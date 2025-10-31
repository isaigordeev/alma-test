"""
MCP Client with OpenAI Integration
Install: pip install mcp openai
Set environment variable: export OPENAI_API_KEY=your_key_here
"""

import asyncio
import os
import json
from groq import AsyncGroq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI, OpenAI

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def process_tool_calls(session: ClientSession, tool_calls):
    """Process tool calls from OpenAI and return results"""
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        print(f"  🔧 Calling tool: {tool_name}")
        print(f"     Arguments: {tool_args}")

        # Call the MCP tool
        result = await session.call_tool(tool_name, tool_args)

        # Extract text from result
        result_text = "\n".join([content.text for content in result.content])
        print(f"     ✓ Result: {result_text[:100]}...")

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
    session: ClientSession, user_message: str, model: str = "gpt-4o-mini"
):
    """Run a chat completion with tool calling"""
    print(f"\n{'=' * 60}")
    print(f"💬 User: {user_message}")
    print(f"{'=' * 60}\n")

    # Get available tools from MCP server
    tools_response = await session.list_tools()

    # Convert MCP tools to OpenAI format
    openai_tools = []
    for tool in tools_response.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
        )

    # Initialize conversation
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant with access to various tools. Use them to answer user questions.",
        },
        {"role": "user", "content": user_message},
    ]

    print("🤖 AI is thinking...\n")

    # Main loop for handling tool calls
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call OpenAI API
        # response = await openai_client.chat.completions.create(
        #     model=model,
        #     messages=messages,
        #     tools=openai_tools,
        #     tool_choice="auto",
        # )
        response = await AsyncGroq(
            api_key=os.getenv("GROQ_API_KEY")
        ).chat.completions.create(
            model="openai/gpt-oss-20b",
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
            print(
                f"🔄 Iteration {iteration + 1}: Processing {len(assistant_message.tool_calls)} tool call(s)\n"
            )

            # Execute all tool calls
            tool_results = await process_tool_calls(
                session, assistant_message.tool_calls
            )

            # Add tool results to messages
            messages.extend(tool_results)

            print()
        else:
            # No more tool calls, we have the final answer
            print(f"✅ Final Answer:\n")
            print(f"🤖 Assistant: {assistant_message.content}\n")
            return assistant_message.content

    print("⚠️ Max iterations reached")
    return assistant_message.content


async def stream_chat_with_tools(
    session: ClientSession, user_message: str, model: str = "gpt-4.1"
):
    """Run a streaming chat completion with tool calling"""
    print(f"\n{'=' * 60}")
    print(f"💬 User: {user_message}")
    print(f"{'=' * 60}\n")

    # Get available tools from MCP server
    tools_response = await session.list_tools()

    # Convert MCP tools to OpenAI format
    openai_tools = []
    for tool in tools_response.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
        )

    # Initialize conversation
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant with access to various tools. Use them to answer user questions.",
        },
        {"role": "user", "content": user_message},
    ]

    print("🤖 AI (streaming): ", end="", flush=True)

    # Main loop for handling tool calls
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call OpenAI API with streaming
        stream = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            stream=True,
        )

        # Collect streamed response
        full_content = ""
        tool_calls_data = {}

        for chunk in stream:
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

        print("itt", iteration, messages[-1])
        # Check if we need to call tools
        if tool_calls_list:
            print(f"\n🔄 Processing {len(tool_calls_list)} tool call(s)...\n")

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
            tool_results = await process_tool_calls(session, tool_call_objects)

            # Add tool results to messages
            messages.extend(tool_results)

            print(f"\n🤖 final tools msgs {messages}", end="", flush=True)
        else:
            # No more tool calls, we have the final answer
            print()
            return full_content

    print("\n⚠️ Max iterations reached")
    return full_content


async def run_client():
    """Run the MCP client with OpenAI integration"""

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Set it with: export OPENAI_API_KEY=your_key_here")
        return

    # Define server parameters
    server_params = StdioServerParameters(
        command="python", args=["mcp-server.py"], env=None
    )

    print("🚀 Starting MCP client with OpenAI integration...\n")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            print("✅ Connected to MCP server\n")

            # Example 1: Simple query requiring one tool
            # await chat_with_tools(session, "What's the weather like in Tokyo?")

            # # Example 2: Complex query requiring multiple tools
            # await chat_with_tools(
            #     session,
            #     "What's the weather in New York, what time is it there, and what's 15% of 250?",
            # )

            # Example 3: Streaming response with tools
            # await stream_chat_with_tools(
            #     session,
            #     "Tell me the weather in London and calculate the sum of 123 + 456 + 789",
            # )

            # Example 4: Query that needs sequential tool calls
            await stream_chat_with_tools(
                session,
                "Compare the weather between San Francisco and Seattle, then calculate which temperature is higher by how many degrees. Before calling a function write a little message about the function and a little resume at the end.",
            )

            print("\n" + "=" * 60)
            print("✅ All conversations completed!")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_client())
