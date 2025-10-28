import  express,  {Request, Response } from 'express';
import { randomUUID } from 'node:crypto';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { z } from 'zod';
import cors from 'cors';
import { isInitializeRequest, CallToolResult } from '@modelcontextprotocol/sdk/types.js';

// ------------------- MCP Server -------------------
export const getServer = () => {
  const server = new McpServer({ name: 'alma-test-server', version: '1.0.0' });

  const emptyInput = {};
  const textOutput = { text: z.string() };

  // createNewChat
  server.tool(
    'createNewChat',
    'Create a new conversation. Only used if explicitly mentioned by the user.',
    emptyInput,
    async (): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: 'A new conversation has been started successfully.' }],
      structuredContent: { text: 'A new conversation started' },
    })
  );

  // navigateToPage
  server.tool(
    'navigateToPage',
    `Navigate to a new application or page. Available pages are:
- home: go to the home page
- chat: chat with the assistant (LLM)
- explore: find information on the internet using LLMs
- scribe: write, edit, and create text
- trad: translate text, documents, and files
- recap: record a meeting and get a summary
- docs: interact with your documents, files, and collections
- actu: read the news`,
    { page: z.enum(['home', 'chat', 'explore', 'scribe', 'trad', 'recap', 'docs', 'actu']) },
    async ({ page }): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: `Navigated to **${page}** page successfully.` }],
      structuredContent: { page },
    })
  );

  server.tool(
    'sendMessage',
    'Send a message to the assistant (chat/assistant). Used when the user explicitly requests an action such as search, ask, what, or how. The query should be reformulated into the best possible prompt in the same language.',
    { message: z.string() },
    async ({ message }): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: `Message sent to assistant:\n> ${message}` }],
      structuredContent: { message },
    })
  );

  server.tool(
    'refreshAssistantMessage',
    'Ask the LLM the question again. Only used if the user explicitly requests it.',
    emptyInput,
    async (): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: 'Assistant message has been refreshed.' }],
      structuredContent: { refreshed: true },
    })
  );

  server.tool(
    'selectModel',
    'Choose a specific LLM model to use. Available models: mistral-large, gpt-4o, llama-3-70b-instruct, claude-3.7-sonnet, google/gemini-1.5-pro-002.',
    { modelName: z.enum(['mistral-large', 'gpt-4o', 'llama-3-70b-instruct', 'claude-3.7-sonnet', 'google/gemini-1.5-pro-002']) },
    async ({ modelName }): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: `Model switched to **${modelName}**.` }],
      structuredContent: { modelName },
    })
  );

  server.tool(
    'toggleEcoMode',
    'Activate or deactivate eco mode.',
    emptyInput,
    async (): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: '🌿 Eco Mode has been toggled.' }],
      structuredContent: { ecoMode: true },
    })
  );

  server.tool(
    'displayMemoryManager',
    'Display the memory manager for a specific category. Available categories: userProfile, companyProfile, communication, tasks, memoryItems, history, contacts.',
    { category: z.enum(['userProfile', 'companyProfile', 'communication', 'tasks', 'memoryItems', 'history', 'contacts']) },
    async ({ category }): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: `🧠 Displaying Memory Manager for **${category}**.` }],
      structuredContent: { category },
    })
  );

  server.tool(
    'closeMemoryManager',
    'Close the memory manager window.',
    emptyInput,
    async (): Promise<CallToolResult> => ({
      content: [{ type: 'text', text: '❌ Memory Manager closed.' }],
      structuredContent: { closed: true },
    })
  );

  return server;
};

// ------------------- Express + HTTP Transport -------------------
const app = express();
app.use(express.json());
app.use(
  cors({
    origin: '*',
    exposedHeaders: ['Mcp-Session-Id']
  })
);

// Map to store transports per session
const transports: { [sessionId: string]: StreamableHTTPServerTransport } = {};

app.post('/mcp', async (req: Request, res: Response) => {
  console.log('[DEBUG] /mcp request received:', req.body);

  try {
    const sessionId = req.headers['mcp-session-id'] as string | undefined;
    let transport: StreamableHTTPServerTransport;

    if (sessionId && transports[sessionId]) {
      transport = transports[sessionId];
      console.log(`[DEBUG] Using existing transport for session ${sessionId}`);
    } else if (!sessionId && isInitializeRequest(req.body)) {
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        enableJsonResponse: true,
        onsessioninitialized: newSessionId => {
          console.log(`[DEBUG] Session initialized: ${newSessionId}`);
          transports[newSessionId] = transport;
        }
      });

      const server = getServer();
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      return; // already handled
    } else {
      res.status(400).json({
        jsonrpc: '2.0',
        error: { code: -32000, message: 'Bad Request: No valid session ID provided' },
        id: null
      });
      return;
    }

    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error('[ERROR] Failed to handle MCP request:', error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: '2.0',
        error: { code: -32603, message: 'Internal server error' },
        id: null
      });
    }
  }
});

// Disallow GET requests
app.get('/mcp', (_req, res) => {
  res.status(405).set('Allow', 'POST').send('Method Not Allowed');
});

// Start server
const PORT = parseInt(process.env.PORT || '3000');
app.listen(PORT, error => {
  if (error) {
    console.error('[ERROR] Failed to start server:', error);
    process.exit(1);
  }
  console.log(`[DEBUG] MCP Streamable HTTP Server listening on port ${PORT}`);
});

process.on('SIGINT', () => {
  console.log('[DEBUG] Shutting down MCP server...');
  process.exit(0);
});
