"""
MCP Server with SSE (Server-Sent Events) over HTTP
Install: pip install mcp aiohttp aiohttp-sse
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict
from aiohttp import web
from aiohttp_sse import sse_response
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mcp-server")

# Create server instance
app = Server("example-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    logger.info("📋 Received request: list_tools")
    tools = [
        Tool(
            name="createNewChat",
            description="Create a new conversation. Only used if explicitly mentioned by the user.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="navigateToPage",
            description=(
                "Navigate to a new application or page. Available pages are:\n"
                "- home: go to the home page\n"
                "- chat: chat with the assistant (LLM)\n"
                "- explore: find information on the internet using LLMs\n"
                "- scribe: write, edit, and create text\n"
                "- trad: translate text, documents, and files\n"
                "- recap: record a meeting and get a summary\n"
                "- docs: interact with your documents, files, and collections\n"
                "- actu: read the news"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "description": "The page to navigate to",
                        "enum": [
                            "home",
                            "chat",
                            "explore",
                            "scribe",
                            "trad",
                            "recap",
                            "docs",
                            "actu",
                        ],
                    }
                },
                "required": ["page"],
            },
        ),
        Tool(
            name="sendMessage",
            description=(
                "Send a message to the assistant (chat/assistant). "
                "Used when the user explicitly requests an action such as search, ask, what, or how. "
                "The query should be reformulated into the best possible prompt in the same language."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to send to the assistant.",
                    }
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="refreshAssistantMessage",
            description="Ask the LLM the question again. Only used if the user explicitly requests it.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="selectModel",
            description=(
                "Choose a specific LLM model to use. "
                "Available models: mistral-large, gpt-4o, llama-3-70b-instruct, claude-3.7-sonnet, google/gemini-1.5-pro-002."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "modelName": {
                        "type": "string",
                        "description": "The name of the model to select.",
                        "enum": [
                            "mistral-large",
                            "gpt-4o",
                            "llama-3-70b-instruct",
                            "claude-3.7-sonnet",
                            "google/gemini-1.5-pro-002",
                        ],
                    }
                },
                "required": ["modelName"],
            },
        ),
        Tool(
            name="toggleEcoMode",
            description="Activate or deactivate eco mode.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="displayMemoryManager",
            description=(
                "Display the memory manager for a specific category. "
                "Available categories: userProfile, companyProfile, communication, tasks, memoryItems, history, contacts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "The memory manager category to display.",
                        "enum": [
                            "userProfile",
                            "companyProfile",
                            "communication",
                            "tasks",
                            "memoryItems",
                            "history",
                            "contacts",
                        ],
                    }
                },
                "required": ["category"],
            },
        ),
        Tool(
            name="closeMemoryManager",
            description="Close the memory manager window.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]
    logger.info(f"✅ Returning {len(tools)} tools")
    return tools


@app.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""
    logger.info(f"🔧 Tool call received: {name}")
    logger.debug(f"   Arguments: {json.dumps(arguments, indent=2)}")

    start_time = datetime.now()

    try:
        # --- Conversation tools ---
        if name == "createNewChat":
            logger.info("   🆕 Creating a new conversation")
            await asyncio.sleep(0.1)
            return [
                TextContent(
                    type="text",
                    text="🆕 A new conversation has been started successfully.",
                )
            ]

        elif name == "sendMessage":
            message = arguments.get("message", "").strip()
            if not message:
                return [
                    TextContent(type="text", text="⚠️ No message provided.")
                ]
            logger.info(f"   💬 Sending message to assistant: {message}")
            await asyncio.sleep(0.15)
            return [
                TextContent(
                    type="text",
                    text=f"📨 Message sent to assistant:\n> {message}",
                )
            ]

        elif name == "refreshAssistantMessage":
            logger.info("   🔄 Refreshing assistant message")
            await asyncio.sleep(0.1)
            return [
                TextContent(
                    type="text",
                    text="🔄 Assistant message has been refreshed.",
                )
            ]
        elif name == "navigateToPage":
            page = arguments.get("page", "").strip()
            valid_pages = [
                "home",
                "chat",
                "explore",
                "scribe",
                "trad",
                "recap",
                "docs",
                "actu",
            ]
            if page not in valid_pages:
                logger.warning(f"   ⚠️ Invalid page requested: {page}")
                return [
                    TextContent(
                        type="text",
                        text=f"❌ Invalid page '{page}'. Please choose one of: {', '.join(valid_pages)}.",
                    )
                ]
            logger.info(f"   🧭 Navigating to page: {page}")
            await asyncio.sleep(0.1)  # simulate navigation
            return [
                TextContent(
                    type="text",
                    text=f"🧭 Navigated to **{page}** page successfully.",
                )
            ]
        elif name == "selectModel":
            model = arguments.get("modelName", "").strip()
            logger.info(f"   🧠 Selecting model: {model}")
            await asyncio.sleep(0.15)
            valid_models = [
                "mistral-large",
                "gpt-4o",
                "llama-3-70b-instruct",
                "claude-3.7-sonnet",
                "google/gemini-1.5-pro-002",
            ]
            if model not in valid_models:
                return [
                    TextContent(
                        type="text", text=f"❌ Unknown model '{model}'."
                    )
                ]
            return [
                TextContent(
                    type="text",
                    text=f"✅ Model successfully switched to **{model}**.",
                )
            ]

        elif name == "toggleEcoMode":
            logger.info("   🌿 Toggling Eco Mode")
            await asyncio.sleep(0.1)
            return [
                TextContent(type="text", text="🌿 Eco Mode has been toggled.")
            ]

        elif name == "displayMemoryManager":
            category = arguments.get("category", "").strip()
            logger.info(
                f"   📂 Displaying memory manager for category: {category}"
            )
            valid_categories = [
                "userProfile",
                "companyProfile",
                "communication",
                "tasks",
                "memoryItems",
                "history",
                "contacts",
            ]
            if category not in valid_categories:
                return [
                    TextContent(
                        type="text", text=f"❌ Invalid category '{category}'."
                    )
                ]
            await asyncio.sleep(0.2)
            return [
                TextContent(
                    type="text",
                    text=f"🧠 Memory Manager opened for **{category}**.",
                )
            ]

        elif name == "closeMemoryManager":
            logger.info("   ❎ Closing memory manager")
            await asyncio.sleep(0.1)
            return [
                TextContent(
                    type="text", text="❎ Memory Manager has been closed."
                )
            ]

        # --- Unknown tool fallback ---
        logger.warning(f"   ⚠️ Unknown tool requested: {name}")
        return [
            TextContent(
                type="text",
                text=f"⚠️ Tool '{name}' not found or unsupported.\n"
                "Please check the tool name or try another action.",
            )
        ]

    except Exception as e:
        logger.error(f"   ❌ Tool execution error: {str(e)}", exc_info=True)
        return [
            TextContent(
                type="text",
                text=f"❌ An error occurred while running '{name}': {str(e)}",
            )
        ]

    finally:
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"   ⏱️ Tool execution completed in {duration:.3f}s")


# HTTP Handler for MCP over SSE
class MCPHTTPHandler:
    def __init__(self, mcp_server: Server):
        self.mcp_server = mcp_server
        self.logger = logging.getLogger("mcp-http-handler")

    async def handle_sse(self, request: web.Request) -> web.Response:
        """Handle SSE connections for streaming MCP requests"""
        client_id = request.remote
        self.logger.info(f"🔌 New SSE connection from {client_id}")

        async with sse_response(request) as resp:
            try:
                # Send connection established event
                await resp.send(
                    json.dumps({"type": "connection", "status": "established"})
                )

                # Keep connection alive and handle incoming messages
                while True:
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                self.logger.info(
                    f"🔌 SSE connection closed by client {client_id}"
                )
            except Exception as e:
                self.logger.error(f"❌ SSE error for {client_id}: {str(e)}")

        return resp

    async def handle_request(self, request: web.Request) -> web.Response:
        """Handle POST requests for MCP operations"""
        client_id = request.remote
        self.logger.info(f"📨 HTTP request received from {client_id}")

        try:
            data = await request.json()
            method = data.get("method")
            params = data.get("params", {})

            self.logger.info(f"   Method: {method}")
            self.logger.debug(f"   Params: {json.dumps(params, indent=2)}")

            if method == "tools/list":
                tools = await list_tools()
                response_data = {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema,
                        }
                        for tool in tools
                    ]
                }
                self.logger.info(f"   ✓ Returning {len(tools)} tools")
                return web.json_response(response_data)

            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})

                result = await call_tool(name, arguments)

                response_data = {
                    "content": [
                        {"type": content.type, "text": content.text}
                        for content in result
                    ]
                }
                self.logger.info(f"   ✓ Tool call completed successfully")
                return web.json_response(response_data)

            else:
                self.logger.warning(f"   ⚠️ Unknown method: {method}")
                return web.json_response(
                    {"error": f"Unknown method: {method}"}, status=400
                )

        except json.JSONDecodeError as e:
            self.logger.error(f"   ❌ Invalid JSON: {str(e)}")
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            self.logger.error(
                f"   ❌ Request handling error: {str(e)}", exc_info=True
            )
            return web.json_response({"error": str(e)}, status=500)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        self.logger.debug("💚 Health check")
        return web.json_response(
            {"status": "healthy", "timestamp": datetime.now().isoformat()}
        )


async def create_app() -> web.Application:
    """Create and configure the web application"""
    handler = MCPHTTPHandler(app)

    webapp = web.Application()
    webapp.router.add_post("/mcp", handler.handle_request)
    webapp.router.add_get("/mcp/sse", handler.handle_sse)
    webapp.router.add_get("/health", handler.handle_health)

    return webapp


async def main():
    """Run the HTTP server"""
    logger.info("=" * 60)
    logger.info("🚀 Starting MCP HTTP Server with SSE")
    logger.info("=" * 60)

    webapp = await create_app()
    runner = web.AppRunner(webapp)
    await runner.setup()

    host = "0.0.0.0"
    port = 3000

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"")
    logger.info(f"✅ Server running on http://{host}:{port}")
    logger.info(f"   📍 Endpoints:")
    logger.info(f"      POST http://localhost:{port}/mcp - MCP requests")
    logger.info(f"      GET  http://localhost:{port}/mcp/sse - SSE streaming")
    logger.info(f"      GET  http://localhost:{port}/health - Health check")
    logger.info(f"")
    logger.info("=" * 60)
    logger.info("📊 Server ready to accept connections...")
    logger.info("=" * 60)

    # Keep server running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down server...")
        await runner.cleanup()
        logger.info("✅ Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
