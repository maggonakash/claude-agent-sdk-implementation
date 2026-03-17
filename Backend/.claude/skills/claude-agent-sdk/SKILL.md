---
name: claude-agent-sdk
description: "Comprehensive guide for building applications with the Claude Agent SDK (Python and TypeScript). Use when the user is asking about: building agents programmatically with Claude Code, using the query() function or ClaudeSDKClient, custom tools, hooks, session management, structured outputs, MCP integration, permissions, streaming, user approvals, or system prompt customization via the SDK."
---

# Claude Agent SDK

## Overview

The Claude Agent SDK lets you run Claude Code as a subprocess from Python or TypeScript — enabling you to build autonomous agents, automate workflows, and integrate Claude into applications.

**Install:**
```bash
pip install claude-agent-sdk                        # Python
npm install @anthropic-ai/claude-agent-sdk          # TypeScript
```

## query() vs ClaudeSDKClient

| Feature | `query()` | `ClaudeSDKClient` |
|:--------|:----------|:------------------|
| Session | New each time | Reuses same session |
| Multi-turn | ❌ | ✅ |
| Interrupts | ❌ | ✅ |
| Streaming input | ✅ | ✅ |
| Hooks | ✅ | ✅ |
| Custom tools | ✅ | ✅ |
| Use case | One-off tasks | Continuous conversations |

**Quick example (Python):**
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

async def main():
    async for message in query(
        prompt="List files in current directory",
        options=ClaudeAgentOptions(allowed_tools=["Bash", "Read"]),
    ):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Quick example (TypeScript):**
```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "List files in current directory",
  options: { allowedTools: ["Bash", "Read"] }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

## Reference Files

Load the appropriate reference file based on what the user needs:

| Topic | File | When to load |
|:------|:-----|:------------|
| Installation, basic usage, input modes | [references/quick-start.md](references/quick-start.md) | Getting started, `query()` vs `ClaudeSDKClient` details |
| Custom in-process tools | [references/custom-tools.md](references/custom-tools.md) | Building tools with `createSdkMcpServer` / `create_sdk_mcp_server` |
| Hooks (PreToolUse, PostToolUse, etc.) | [references/hooks.md](references/hooks.md) | Intercepting tool calls, blocking/modifying operations, logging |
| Session management & permissions | [references/sessions-permissions.md](references/sessions-permissions.md) | Resume/fork sessions, permission modes |
| Structured outputs | [references/structured-outputs.md](references/structured-outputs.md) | JSON Schema, Zod, Pydantic typed outputs |
| External MCP servers | [references/mcp-integration.md](references/mcp-integration.md) | stdio, HTTP/SSE MCP servers, authentication |
| Streaming output & input | [references/streaming.md](references/streaming.md) | Real-time token streaming, streaming input mode |
| User approvals & clarifying questions | [references/user-input.md](references/user-input.md) | `canUseTool`, `AskUserQuestion` |
| System prompt, CLAUDE.md, Skills | [references/system-prompt.md](references/system-prompt.md) | Customizing Claude's behavior, presets, loading Skills |
