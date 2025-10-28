"""
MCP Server using official SDK
Install: pip install mcp
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio
import mcp.types as types

# Create server instance
app = Server("example-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="get_weather",
            description="Get the current weather for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"],
            },
        ),
        Tool(
            name="calculate",
            description="Perform a mathematical calculation",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="get_time",
            description="Get the current time in a timezone",
            inputSchema={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., UTC, America/New_York)",
                    }
                },
                "required": ["timezone"],
            },
        ),
        Tool(
            name="search_files",
            description="Search for files by pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path to search",
                    },
                },
                "required": ["pattern"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls"""

    if name == "get_weather":
        location = arguments.get("location", "unknown")
        # Simulate some processing time
        await asyncio.sleep(0.2)
        return [
            TextContent(
                type="text",
                text=f"🌤️ Weather in {location}:\n- Temperature: 72°F (22°C)\n- Conditions: Sunny\n- Humidity: 45%\n- Wind: 8 mph",
            )
        ]

    elif name == "calculate":
        expression = arguments.get("expression", "")
        try:
            # Safe evaluation for demo
            result = eval(
                expression,
                {"__builtins__": {}},
                {
                    "abs": abs,
                    "round": round,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "pow": pow,
                },
            )
            await asyncio.sleep(0.1)
            return [
                TextContent(
                    type="text",
                    text=f"📊 Calculation: {expression} = {result}",
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"❌ Error calculating '{expression}': {str(e)}",
                )
            ]

    elif name == "get_time":
        timezone = arguments.get("timezone", "UTC")
        await asyncio.sleep(0.15)
        # Simulate time lookup
        times = {
            "UTC": "14:30:00",
            "America/New_York": "10:30:00",
            "Europe/London": "14:30:00",
            "Asia/Tokyo": "23:30:00",
        }
        time = times.get(timezone, "12:00:00")
        return [
            TextContent(
                type="text", text=f"🕐 Current time in {timezone}: {time}"
            )
        ]

    elif name == "search_files":
        pattern = arguments.get("pattern", "*")
        path = arguments.get("path", ".")
        await asyncio.sleep(0.25)
        # Simulate file search
        files = [
            f"📄 {path}/document1.txt",
            f"📄 {path}/data.json",
            f"📄 {path}/readme.md",
        ]
        return [
            TextContent(
                type="text",
                text=f"🔍 Found {len(files)} files matching '{pattern}':\n"
                + "\n".join(files),
            )
        ]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream, app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
