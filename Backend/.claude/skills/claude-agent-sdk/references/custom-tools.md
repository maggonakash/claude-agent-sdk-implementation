# Custom Tools

Build in-process MCP tools to extend Claude's capabilities.

## Table of Contents
- [Overview](#overview)
- [Define a tool (Python)](#define-a-tool-python)
- [Define a tool (TypeScript)](#define-a-tool-typescript)
- [Use tools in a query](#use-tools-in-a-query)
- [Tool naming convention](#tool-naming-convention)
- [Type-safe schemas](#type-safe-schemas)
- [Error handling](#error-handling)
- [Multiple tools example](#multiple-tools-example)

---

## Overview

Custom tools run in-process with your app — no separate server needed. Use `createSdkMcpServer` (TypeScript) or `create_sdk_mcp_server` (Python) to group tools, then pass the server via `mcpServers`.

> **Important:** Custom MCP tools require **streaming input mode** — use an async generator for `prompt`, not a plain string.

---

## Define a tool (Python)

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any

@tool(
    "get_weather",
    "Get current temperature for a location",
    {"latitude": float, "longitude": float},  # Simple type mapping
)
async def get_weather(args: dict[str, Any]) -> dict[str, Any]:
    # Call external API
    return {
        "content": [{"type": "text", "text": f"Temperature: 72°F"}]
    }

custom_server = create_sdk_mcp_server(
    name="my-tools",
    version="1.0.0",
    tools=[get_weather],
)
```

**Schema formats (Python):**
```python
# Simple type mapping (recommended)
{"param": str, "count": int, "value": float}

# JSON Schema (for enums, required fields, etc.)
{
    "type": "object",
    "properties": {
        "method": {"type": "string", "enum": ["GET", "POST"]},
        "url": {"type": "string"},
    },
    "required": ["method", "url"],
}
```

---

## Define a tool (TypeScript)

```typescript
import { tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const customServer = createSdkMcpServer({
  name: "my-tools",
  version: "1.0.0",
  tools: [
    tool(
      "get_weather",
      "Get current temperature for a location",
      {
        latitude: z.number().describe("Latitude"),
        longitude: z.number().describe("Longitude"),
      },
      async (args) => ({
        content: [{ type: "text", text: `Temperature: 72°F` }]
      })
    )
  ]
});
```

---

## Use tools in a query

```python
# Python
from claude_agent_sdk import query, ClaudeAgentOptions

async def message_generator():
    yield {
        "type": "user",
        "message": {"role": "user", "content": "What's the weather in San Francisco?"},
    }

async for message in query(
    prompt=message_generator(),   # Streaming input required
    options=ClaudeAgentOptions(
        mcp_servers={"my-tools": custom_server},  # Dict, not list
        allowed_tools=["mcp__my-tools__get_weather"],
    ),
):
    if hasattr(message, "result"):
        print(message.result)
```

```typescript
// TypeScript
async function* generateMessages() {
  yield {
    type: "user" as const,
    message: { role: "user" as const, content: "What's the weather in SF?" }
  };
}

for await (const message of query({
  prompt: generateMessages(),   // Streaming input required
  options: {
    mcpServers: { "my-tools": customServer },  // Object, not array
    allowedTools: ["mcp__my-tools__get_weather"],
  }
})) {
  if (message.type === "result") console.log(message.result);
}
```

---

## Tool naming convention

MCP tools are named: `mcp__{server_name}__{tool_name}`

- Server `"my-tools"`, tool `"get_weather"` → `mcp__my-tools__get_weather`
- Use wildcard to allow all tools from a server: `"mcp__my-tools__*"`

---

## Type-safe schemas

```python
# Python — use JSON Schema for complex validation
@tool(
    "process",
    "Process data",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0},
            "format": {"type": "string", "enum": ["json", "csv"], "default": "json"},
        },
        "required": ["name"],
    },
)
async def process(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Processed {args['name']}"}]}
```

---

## Error handling

Return error messages in the `content` field — don't raise exceptions:

```python
@tool("fetch_data", "Fetch from API", {"url": str})
async def fetch_data(args: dict[str, Any]) -> dict[str, Any]:
    try:
        # ... fetch logic
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}
```

---

## Multiple tools example

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any

@tool("calculate", "Perform math", {"expression": str})
async def calculate(args: dict[str, Any]) -> dict[str, Any]:
    result = eval(args["expression"], {"__builtins__": {}})
    return {"content": [{"type": "text", "text": f"Result: {result}"}]}

@tool("translate", "Translate text", {"text": str, "target_lang": str})
async def translate(args: dict[str, Any]) -> dict[str, Any]:
    # Translation logic
    return {"content": [{"type": "text", "text": f"Translated: {args['text']}"}]}

server = create_sdk_mcp_server(
    name="utilities",
    version="1.0.0",
    tools=[calculate, translate],
)

# Selectively allow tools
options = ClaudeAgentOptions(
    mcp_servers={"utilities": server},
    allowed_tools=["mcp__utilities__calculate"],  # Only allow calculate
)
```
