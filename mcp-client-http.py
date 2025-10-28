"""
MCP Client with OpenAI Integration over HTTP
Install: pip install openai aiohttp aiohttp-sse
Set environment variable: export OPENAI_API_KEY=your_key_here
"""

import asyncio
import os
import json
import logging
from typing import List, Dict, Any
import aiohttp
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mcp-client")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class MCPHTTPClient:
    """MCP Client using HTTP transport"""

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.session = None
        self.logger = logging.getLogger("mcp-http-client")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        self.logger.info(f"🔌 Connecting to MCP server at {self.base_url}")

        # Test connection
        try:
            async with self.session.get(f"{self.base_url}/health") as resp:
                if resp.status == 200:
                    self.logger.info("✅ Connected to MCP server")
                else:
                    self.logger.warning(
                        f"⚠️ Server responded with status {resp.status}"
                    )
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to server: {str(e)}")
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.logger.info("🔌 Disconnected from MCP server")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server"""
        self.logger.info("📋 Requesting tool list...")

        async with self.session.post(
            f"{self.base_url}/mcp", json={"method": "tools/list", "params": {}}
        ) as resp:
            data = await resp.json()
            tools = data.get("tools", [])
            self.logger.info(f"✅ Received {len(tools)} tools")
            return tools

    async def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on the MCP server"""
        self.logger.info(f"🔧 Calling tool: {name}")
        self.logger.debug(f"   Arguments: {json.dumps(arguments, indent=2)}")

        async with self.session.post(
            f"{self.base_url}/mcp",
            json={
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        ) as resp:
            data = await resp.json()
            self.logger.info(f"✅ Tool call completed: {name}")
            return data


async def process_tool_calls(client: MCPHTTPClient, tool_calls):
    """Process tool calls from OpenAI and return results"""
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        logger.info(f"  🔧 Executing tool: {tool_name}")
        logger.debug(f"     Arguments: {tool_args}")

        # Call the MCP tool
        result = await client.call_tool(tool_name, tool_args)

        # Extract text from result
        result_text = "\n".join(
            [content["text"] for content in result.get("content", [])]
        )
        logger.info(f"     ✓ Result received ({len(result_text)} chars)")

        tool_results.append(
            {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_name,
                "content": result_text,
            }
        )

    return tool_results


async def chat_with_tools(
    client: MCPHTTPClient, user_message: str, model: str = "gpt-4o-mini"
):
    """Run a chat completion with tool calling"""
    logger.info("")
    logger.info(f"{'=' * 60}")
    logger.info(f"💬 User Query: {user_message}")
    logger.info(f"{'=' * 60}")

    # Get available tools from MCP server
    logger.info("📋 Fetching available tools...")
    tools_list = await client.list_tools()

    # Convert MCP tools to OpenAI format
    openai_tools = []
    for tool in tools_list:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            }
        )

    logger.info(f"✅ Loaded {len(openai_tools)} tools for AI")

    # Initialize conversation
    system = """Your name is Alma
  You are the voice assistant of Delos, a platform of AI applications.
  Thanks to you, the user can interact with the platform by voice.
  You must act like Jarvis from Iron Man : being able to answer questions of the user, when he asks you something, 
  and being able to perform different tasks on the platform."""
    # Initialize conversation
    messages = [
        {
            "role": "system",
            "content": system,
        },
        {"role": "user", "content": user_message},
    ]
    logger.info("🤖 Sending request to OpenAI...")

    # Main loop for handling tool calls
    max_iterations = 5
    for iteration in range(max_iterations):
        logger.info(f"🔄 Iteration {iteration + 1}/{max_iterations}")

        # Call OpenAI API
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        # Add assistant message to conversation
        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (assistant_message.tool_calls or [])
                ]
                if assistant_message.tool_calls
                else None,
            }
        )

        # Check if we need to call tools
        if assistant_message.tool_calls:
            logger.info(
                f"🛠️  AI requested {len(assistant_message.tool_calls)} tool call(s)"
            )

            # Execute all tool calls
            tool_results = await process_tool_calls(
                client, assistant_message.tool_calls
            )

            # Add tool results to messages
            messages.extend(tool_results)
            logger.info(f"[CONVERSATION] {messages}")
            logger.info("✅ All tool results added to conversation")
        else:
            # No more tool calls, we have the final answer
            logger.info("✅ Final answer received from AI")
            logger.info("")
            logger.info(f"🤖 Assistant: {assistant_message.content}")
            logger.info("")
            return assistant_message.content

    logger.warning("⚠️ Max iterations reached")
    return assistant_message.content


async def stream_chat_with_tools(
    client: MCPHTTPClient, user_message: str, model: str = "gpt-4o-mini"
):
    """Run a streaming chat completion with tool calling"""
    logger.info("")
    logger.info(f"{'=' * 60}")
    logger.info(f"💬 User Query (Streaming): {user_message}")
    logger.info(f"{'=' * 60}")

    # Get available tools from MCP server
    logger.info("📋 Fetching available tools...")
    tools_list = await client.list_tools()

    print(tools_list)

    # Convert MCP tools to OpenAI format
    openai_tools = []
    for tool in tools_list:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            }
        )

    logger.info(f"✅ Loaded {len(openai_tools)} tools for AI")

    # Initialize conversation
    system = """Your name is Alma
  You are the voice assistant of Delos, a platform of AI applications.
  Thanks to you, the user can interact with the platform by voice.
  You must act like Jarvis from Iron Man : being able to answer questions of the user, when he asks you something, 
  and being able to perform different tasks on the platform."""
    # Initialize conversation
    messages = [
        {
            "role": "system",
            "content": system,
        },
        {"role": "user", "content": user_message},
    ]

    logger.info("🤖 Streaming response from OpenAI...")
    print("\n🤖 Assistant: ", end="", flush=True)

    # Main loop for handling tool calls
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call OpenAI API with streaming
        stream = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            stream=True,
        )

        # Collect streamed response
        full_content = ""
        tool_calls_data = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta

            # Stream text content
            if delta.content:
                print(delta.content, end="", flush=True)
                full_content += delta.content

            # Collect tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    if tc.id:
                        tool_calls_data[idx]["id"] = tc.id
                    if tc.function.name:
                        tool_calls_data[idx]["function"]["name"] = (
                            tc.function.name
                        )
                    if tc.function.arguments:
                        tool_calls_data[idx]["function"]["arguments"] += (
                            tc.function.arguments
                        )

        print()  # New line after streaming

        # Convert tool_calls_data to list
        tool_calls_list = (
            [tool_calls_data[i] for i in sorted(tool_calls_data.keys())]
            if tool_calls_data
            else None
        )

        # Add assistant message to conversation
        messages.append(
            {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": tool_calls_list,
            }
        )

        # Check if we need to call tools
        if tool_calls_list:
            logger.info(f"🛠️  AI requested {len(tool_calls_list)} tool call(s)")

            # Create tool call objects for processing
            class ToolCall:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.function = type(
                        "Function",
                        (),
                        {
                            "name": data["function"]["name"],
                            "arguments": data["function"]["arguments"],
                        },
                    )()

            tool_call_objects = [ToolCall(tc) for tc in tool_calls_list]

            # Execute all tool calls
            tool_results = await process_tool_calls(client, tool_call_objects)

            # Add tool results to messages
            messages.extend(tool_results)
            logger.info("✅ All tool results added to conversation")

            logger.info(f"[STREAM CONVERSATION] {messages}")
            print("\n🤖 Assistant: ", end="", flush=True)
        else:
            # No more tool calls, we have the final answer
            logger.info("✅ Streaming conversation completed")
            print()
            return full_content

    logger.warning("⚠️ Max iterations reached")
    print()
    return full_content


async def main():
    """Run the MCP client with OpenAI integration"""

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY environment variable not set")
        logger.error("Set it with: export OPENAI_API_KEY=your_key_here")
        return

    logger.info("=" * 60)
    logger.info("🚀 Starting MCP HTTP Client with OpenAI")
    logger.info("=" * 60)

    async with MCPHTTPClient() as client:
        # Example 1: Simple query requiring one tool
        # await chat_with_tools(client, "What's the weather like in Tokyo?")

        # Example 2: Complex query requiring multiple tools
        # await chat_with_tools(
        #     client,
        #     "What's the weather in New York, what time is it there, and what's 15% of 250?",
        # )

        # Example 3: Streaming response with tools
        # await stream_chat_with_tools(
        #     client,
        #     "Tell me the weather in London and calculate the sum of 123 + 456 + 789",
        # )

        # Example 4: Query that needs sequential tool calls
        await stream_chat_with_tools(client, "What can you do on the page?")

        logger.info("")
        logger.info("=" * 60)

        logger.info("✅ All conversations completed!")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
