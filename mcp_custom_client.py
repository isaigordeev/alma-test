from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import uvicorn
from rtc_client import rtc_client


import asyncio
import os
import json
import logging
from datetime import timedelta
from typing import Any, Dict, List
from groq import AsyncGroq
from openai import AsyncOpenAI
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mcp-client")

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SERVER_URL = "http://localhost:3000/mcp"
TIMEOUT = timedelta(seconds=60)


# ---------------------------------------------------------------------------- #
#                                Helper Functions                              #
# ---------------------------------------------------------------------------- #
async def process_tool_calls(session: ClientSession, tool_calls):
    """Execute tool calls received from OpenAI and return results"""
    tool_results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments or "{}")

        logger.info(f"🔧 Executing MCP tool: {tool_name}, {tool_args}")
        result = await session.call_tool(tool_name, tool_args)

        # Extract result text
        content = []
        if hasattr(result, "content"):
            for c in result.content:
                if getattr(c, "type", None) == "text":
                    content.append(c.text)
                else:
                    content.append(str(c))

        result_text = "\n".join(content)
        logger.info(
            f"✅ Tool '{tool_name}' completed ({len(result_text)} chars)"
        )

        tool_results.append(
            {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_name,
                "content": result_text,
            }
        )
    return tool_results


async def build_openai_tools(session: ClientSession) -> List[Dict[str, Any]]:
    """Fetch MCP tools and convert to OpenAI tool schema"""
    logger.info("📋 Listing available MCP tools...")
    tools_resp = await session.list_tools()
    tools = tools_resp.tools if hasattr(tools_resp, "tools") else []

    if not tools:
        logger.warning("⚠️ No tools available from MCP server.")
        return []

    logger.info(f"✅ Loaded {len(tools)} tools")
    openai_tools = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": getattr(tool, "input_schema", {}) or {},
                },
            }
        )
    return openai_tools


# ---------------------------------------------------------------------------- #
#                            Chat / Stream Functions                           #
# ---------------------------------------------------------------------------- #
async def chat_with_tools(
    session: ClientSession, user_message: str, model="gpt-4o-mini"
):
    """Run OpenAI chat completion with MCP tool calling"""
    logger.info("\n" + "=" * 60)
    logger.info(f"💬 User Query: {user_message}")
    logger.info("=" * 60)

    tools = await build_openai_tools(session)
    messages = [
        {
            "role": "system",
            "content": (
                "You are Alma, the voice assistant of Delos, a platform of AI applications. "
                "You can answer user questions and execute platform tools as needed."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    for iteration in range(5):
        logger.info(f"🔄 Iteration {iteration + 1}/5")
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="required",
        )

        message = response.choices[0].message
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (message.tool_calls or [])
                ]
                if message.tool_calls
                else None,
            }
        )

        if message.tool_calls:
            logger.info(
                f"🛠️  AI requested {len(message.tool_calls)} tool call(s)"
            )
            tool_results = await process_tool_calls(
                session, message.tool_calls
            )
            messages.extend(tool_results)
        else:
            logger.info("✅ Final AI response:")
            print(f"\n🤖 Alma: {message.content}\n")
            return message.content

    logger.warning("⚠️ Max iterations reached without final response.")
    return None


async def stream_chat_with_tools(
    session: ClientSession, user_message: str, model="gpt-4o-mini"
):
    """Run a streaming OpenAI chat completion with MCP tool calling"""
    logger.info("\n" + "=" * 60)
    logger.info(f"💬 Streaming Query: {user_message}")
    logger.info("=" * 60)

    tools = await session.list_tools()

    openai_tools = []
    for tool in tools.tools:
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

    messages = [
        {
            "role": "system",
            "content": (
                "You are Alma, the voice assistant of Delos, a platform of AI applications. "
                "You can answer user questions and execute platform tools as needed. You can also answer with a short human phase before actions that you would execute them."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    print("\n🤖 Alma: ", end="", flush=True)
    for iteration in range(5):
        tool_calls_data = {}
        full_content = ""

        stream = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            stream=True,
        )
        # stream = await AsyncGroq(
        #     api_key=os.getenv("GROQ_API_KEY")
        # ).chat.completions.create(
        #     model="openai/gpt-oss-120b",
        #     messages=messages,
        #     tools=openai_tools,
        #     tool_choice="auto",
        #     stream=True,
        # )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
                full_content += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    tool_calls_data.setdefault(
                        idx,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
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

        print()  # newline after stream

        tool_calls_list = (
            [tool_calls_data[i] for i in sorted(tool_calls_data.keys())]
            if tool_calls_data
            else None
        )
        messages.append(
            {
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": tool_calls_list,
            }
        )

        if tool_calls_list:
            logger.info(f"🧩 {len(tool_calls_list)} tool call(s) detected")

            class ToolCall:
                def __init__(self, d):
                    self.id = d["id"]
                    self.type = d["type"]
                    self.function = type(
                        "Function",
                        (),
                        {
                            "name": d["function"]["name"],
                            "arguments": d["function"]["arguments"],
                        },
                    )()

            tool_objects = [ToolCall(tc) for tc in tool_calls_list]
            results = await process_tool_calls(session, tool_objects)
            messages.extend(results)
            print("\n🤖 Alma: ", end="", flush=True)

            print()  # newline after stream
            logger.info(f"CONV {messages}")
            print(full_content)
        else:
            print()
            logger.info("✅ Streamed conversation complete.")
            return full_content

    logger.warning("⚠️ Max iterations reached in stream mode.")
    print()
    return full_content


# ---------------------------------------------------------------------------- #
#                                   Main Run                                   #
# ---------------------------------------------------------------------------- #

pcs = set()

recognizers = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (optional)
    print("Server starting...")
    yield
    # Shutdown code
    print("Server shutting down...")
    for pc in pcs:
        await pc.close()
        recognizer, push_stream = recognizers[pc]
        push_stream.close()
        recognizer.stop_continuous_recognition()


app = FastAPI(lifespan=lifespan)

# Allow all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # You can set specific origins like ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

channels = {}  # mutable container
channel_ready = asyncio.Future()


@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    logger.info("[LOG] RTCPeerConnection created.")

    # Queues for communication
    queue_in: asyncio.Queue = asyncio.Queue()

    # --- Data Channels from Browser ---
    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        logger.info(f"[LOG] Data channel received: {channel.label}")

        if channel.label == "text-out":
            logger.info("[LOG] Server received mcp_read channel")
            channel.on("message", lambda msg: queue_in.put_nowait(msg))
            channels["out"] = channel

            if not channel_ready.done():
                channel_ready.set_result(True)

    # --- Set Remote Description and Create Answer ---
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    logger.info("[LOG] SDP answer created and set.")

    # --- Initialize MCP Client ---
    async def run_mcp_client():
        await channel_ready
        print(channels)
        logger.info("[MCP] Initializing MCP session...")
        async with rtc_client(queue_in, channels["out"]) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("[MCP] Wants to connect")
                await session.initialize()
                logger.info("[MCP] Connected to MCP server (Session ID:)")
                await stream_chat_with_tools(
                    session, "Create a new note in Scribe."
                )

    asyncio.create_task(run_mcp_client())

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


if __name__ == "__main__":
    print("[LOG] Starting FastAPI server on http://0.0.0.0:8080")
    uvicorn.run(
        "mcp_custom_client:app", host="0.0.0.0", port=8080, reload=True
    )
