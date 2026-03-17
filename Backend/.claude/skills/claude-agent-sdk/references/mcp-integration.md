# External MCP Integration

Connect to external tools and data sources via the Model Context Protocol.

## Table of Contents
- [Overview](#overview)
- [Transport types](#transport-types)
  - [stdio servers](#stdio-servers)
  - [HTTP/SSE servers](#httpsse-servers)
- [Allow MCP tools](#allow-mcp-tools)
- [Authentication](#authentication)
- [MCP tool search](#mcp-tool-search)
- [Error handling](#error-handling)
- [Troubleshooting](#troubleshooting)

---

## Overview

MCP servers extend Claude with external tools (databases, APIs, filesystems). Configure via `mcp_servers` / `mcpServers` in options or in a `.mcp.json` file at project root.

For in-process tools defined in your own code, see [custom-tools.md](custom-tools.md).

---

## Transport types

### stdio servers

Local processes communicating via stdin/stdout. Use for servers installed on the same machine.

```python
# Python
options = ClaudeAgentOptions(
    mcp_servers={
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]},
        }
    },
    allowed_tools=["mcp__github__list_issues", "mcp__github__search_issues"],
)
```

```typescript
// TypeScript
const options = {
  mcpServers: {
    github: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-github"],
      env: { GITHUB_TOKEN: process.env.GITHUB_TOKEN }
    }
  },
  allowedTools: ["mcp__github__list_issues"]
};
```

### HTTP/SSE servers

Cloud-hosted or remote MCP servers.

```python
# Python — HTTP
options = ClaudeAgentOptions(
    mcp_servers={
        "remote-api": {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
        }
    },
    allowed_tools=["mcp__remote-api__*"],
)

# SSE (streaming)
options = ClaudeAgentOptions(
    mcp_servers={
        "remote-api": {
            "type": "sse",
            "url": "https://api.example.com/mcp/sse",
            "headers": {"Authorization": f"Bearer {os.environ['API_TOKEN']}"},
        }
    },
    allowed_tools=["mcp__remote-api__*"],
)
```

### From .mcp.json (auto-loaded)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
    },
    "remote-api": {
      "type": "sse",
      "url": "https://api.example.com/mcp/sse",
      "headers": { "Authorization": "Bearer ${API_TOKEN}" }
    }
  }
}
```

---

## Allow MCP tools

MCP tools require explicit permission. Tool naming pattern: `mcp__{server-name}__{tool-name}`

```python
# Python
allowed_tools=[
    "mcp__github__*",            # All tools from github server
    "mcp__db__query",            # Only the query tool from db server
    "mcp__slack__send_message",  # Only send_message from slack server
]
```

Alternatively, use `permissionMode: "acceptEdits"` to skip per-tool permission prompts.

---

## Authentication

### Environment variables (stdio)
```python
"env": {"GITHUB_TOKEN": os.environ["GITHUB_TOKEN"]}
```

### HTTP headers (HTTP/SSE)
```python
"headers": {"Authorization": f"Bearer {token}"}
```

### OAuth2
```python
access_token = await get_access_token_from_oauth_flow()
options = ClaudeAgentOptions(
    mcp_servers={
        "oauth-api": {
            "type": "http",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": f"Bearer {access_token}"},
        }
    }
)
```

---

## MCP tool search

When many MCP tools would consume >10% of the context window, tool search activates automatically (requires Sonnet 4+ or Opus 4+, not Haiku).

Control with `ENABLE_TOOL_SEARCH` env var:

| Value | Behavior |
|:------|:---------|
| `auto` | Activates at 10% threshold (default) |
| `auto:5` | Activates at 5% threshold |
| `true` | Always enabled |
| `false` | Disabled, all tools loaded upfront |

```python
options = ClaudeAgentOptions(
    mcp_servers={...},
    env={"ENABLE_TOOL_SEARCH": "auto:5"},
)
```

---

## Error handling

Check the `system` init message for connection failures:

```python
async for message in query(prompt=..., options=options):
    if isinstance(message, SystemMessage) and message.subtype == "init":
        failed = [s for s in message.data.get("mcp_servers", []) if s.get("status") != "connected"]
        if failed:
            print(f"Failed servers: {failed}")
    if isinstance(message, ResultMessage) and message.subtype == "error_during_execution":
        print("Execution failed")
```

---

## Troubleshooting

**Server shows "failed" status:**
- Check env variables are set
- Verify the `npx` package exists and Node.js is in PATH
- Check the URL is reachable for HTTP/SSE servers

**Tools not being called:**
- Ensure `allowedTools` includes the tool or use `"mcp__servername__*"` wildcard
- Tools without permission in `allowedTools` are visible but not callable

**Connection timeout:**
- Default timeout is 60s; pre-warm servers before starting the agent

**Discover available tools** from init message:
```python
if isinstance(message, SystemMessage) and message.subtype == "init":
    print("MCP tools:", message.data.get("mcp_servers"))
```
