# Quick Start & Input Modes

## Table of Contents
- [Installation](#installation)
- [query() — one-shot tasks](#query--one-shot-tasks)
- [ClaudeSDKClient — continuous conversations](#claudesdkclient--continuous-conversations)
- [Input modes](#input-modes)
- [Common options](#common-options)
- [Message types](#message-types)

---

## Installation

```bash
pip install claude-agent-sdk                        # Python
npm install @anthropic-ai/claude-agent-sdk          # TypeScript
```

---

## query() — one-shot tasks

Creates a new session per call. Best for automation scripts, independent tasks, one-off queries.

```python
# Python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

async def main():
    async for message in query(
        prompt="Summarize the README",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob"],
            max_turns=5,
        ),
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)

asyncio.run(main())
```

```typescript
// TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Summarize the README",
  options: { allowedTools: ["Read", "Glob"], maxTurns: 5 }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

---

## ClaudeSDKClient — continuous conversations

Reuses the same session. Best for chat interfaces, multi-turn workflows, when you need interrupts.

```python
# Python
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock

async def main():
    options = ClaudeAgentOptions(allowed_tools=["Read", "Write", "Bash"])
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Set up a Python project")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)

asyncio.run(main())
```

```typescript
// TypeScript — use query() with ClaudeSDKClient for multi-turn
import { ClaudeSDKClient } from "@anthropic-ai/claude-agent-sdk";

const client = new ClaudeSDKClient({ allowedTools: ["Read", "Write", "Bash"] });
await client.connect();

for await (const message of client.query("Set up a Python project")) {
  if (message.type === "assistant") {
    console.log(message.message.content);
  }
}
```

---

## Input modes

### Single message (simple)
Pass a plain string as `prompt`. Works for simple stateless tasks but doesn't support images, hooks, or dynamic queuing.

### Streaming input (recommended)
Pass an async generator as `prompt`. Required for custom MCP tools, hooks/`canUseTool`, and rich interactions.

```python
# Python — streaming input
async def message_generator():
    yield {
        "type": "user",
        "message": {"role": "user", "content": "Analyze this codebase for security issues"},
    }
    # Optionally yield follow-up messages dynamically

async for message in query(prompt=message_generator(), options=options):
    ...
```

```typescript
// TypeScript — streaming input
async function* generateMessages() {
  yield {
    type: "user" as const,
    message: { role: "user" as const, content: "Analyze this codebase for security issues" }
  };
}

for await (const message of query({ prompt: generateMessages(), options })) { ... }
```

> **Note:** Custom MCP tools (`mcpServers`) require streaming input mode. A plain string prompt will NOT work.

---

## Common options

| Python | TypeScript | Type | Description |
|:-------|:-----------|:-----|:------------|
| `allowed_tools` | `allowedTools` | `string[]` | Tools Claude can use (e.g. `["Read", "Write", "Bash"]`) |
| `max_turns` | `maxTurns` | `number` | Max agent turns before stopping |
| `model` | `model` | `string` | Model ID (e.g. `"claude-opus-4-6"`) |
| `cwd` | `cwd` | `string` | Working directory |
| `permission_mode` | `permissionMode` | `string` | `"default"`, `"acceptEdits"`, `"bypassPermissions"`, `"plan"` |
| `system_prompt` | `systemPrompt` | `string\|object` | Override or append to system prompt |
| `setting_sources` | `settingSources` | `string[]` | Load `"user"` and/or `"project"` settings (CLAUDE.md, skills, hooks) |
| `mcp_servers` | `mcpServers` | `object` | External MCP server configurations |
| `output_format` | `outputFormat` | `object` | Structured output JSON schema |
| `include_partial_messages` | `includePartialMessages` | `boolean` | Enable streaming output tokens |
| `resume` | `resume` | `string` | Resume from session ID |
| `can_use_tool` | `canUseTool` | `callback` | Runtime permission callback |
| `hooks` | `hooks` | `object` | Lifecycle hook callbacks |

---

## Message types

Messages yielded from `query()` / `client.receive_response()`:

| Type | Subtype | Description |
|:-----|:--------|:------------|
| `system` | `init` | Session start, includes `session_id` and `mcp_servers` |
| `assistant` | — | Claude's response with `content` blocks |
| `result` | `success` | Final result, includes `result` text and optionally `structured_output` |
| `result` | `error_during_execution` | Agent hit an error |
| `result` | `error_max_structured_output_retries` | Couldn't produce valid structured output |
| `stream_event` | — | Raw streaming token event (only when `includePartialMessages: true`) |
| `compact_boundary` | — | Conversation history was compacted |

```python
# Python — check message types
from claude_agent_sdk import SystemMessage, AssistantMessage, ResultMessage
from claude_agent_sdk.types import StreamEvent

async for message in query(prompt=..., options=...):
    if isinstance(message, SystemMessage) and message.subtype == "init":
        session_id = message.data.get("session_id")
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            print(block)
    elif isinstance(message, ResultMessage) and message.subtype == "success":
        print(message.result)
```
