# Streaming

Real-time streaming output and the streaming input mode.

## Table of Contents
- [Streaming output (tokens as they arrive)](#streaming-output)
- [Streaming input mode](#streaming-input-mode)
- [Message flow with streaming enabled](#message-flow)
- [Build a streaming UI](#build-a-streaming-ui)
- [Limitations](#limitations)

---

## Streaming output

Enable with `include_partial_messages=True` / `includePartialMessages: true`. Yields `StreamEvent` messages containing raw API events in addition to normal messages.

```python
# Python — print text as it streams
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent

async def stream_text():
    options = ClaudeAgentOptions(include_partial_messages=True)
    async for message in query(prompt="Explain how databases work", options=options):
        if isinstance(message, StreamEvent):
            event = message.event
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    print(delta.get("text", ""), end="", flush=True)
    print()
```

```typescript
// TypeScript — print text as it streams
for await (const message of query({
  prompt: "Explain how databases work",
  options: { includePartialMessages: true }
})) {
  if (message.type === "stream_event") {
    const event = message.event;
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      process.stdout.write(event.delta.text);
    }
  }
}
```

### StreamEvent structure

```python
# Python
@dataclass
class StreamEvent:
    uuid: str
    session_id: str
    event: dict[str, Any]       # Raw Claude API stream event
    parent_tool_use_id: str | None
```

### Common event types in `event` field

| Event type | Description |
|:-----------|:------------|
| `message_start` | New message begins |
| `content_block_start` | New content block (text or tool_use) |
| `content_block_delta` | Incremental update (`text_delta` or `input_json_delta`) |
| `content_block_stop` | Content block finished |
| `message_delta` | Stop reason, usage info |
| `message_stop` | Message complete |

### Stream tool calls

```python
current_tool = None
tool_input = ""

async for message in query(prompt="Read the README.md", options=ClaudeAgentOptions(
    include_partial_messages=True, allowed_tools=["Read"]
)):
    if isinstance(message, StreamEvent):
        event = message.event
        if event.get("type") == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                current_tool = block.get("name")
                tool_input = ""
                print(f"Starting: {current_tool}")
        elif event.get("type") == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "input_json_delta":
                tool_input += delta.get("partial_json", "")
        elif event.get("type") == "content_block_stop" and current_tool:
            print(f"{current_tool} called with: {tool_input}")
            current_tool = None
```

---

## Streaming input mode

Pass an async generator as `prompt` instead of a plain string. This is the **recommended** input mode — required for custom MCP tools, `canUseTool`, and rich interactions (images, interrupts, queued messages).

```python
# Python
async def message_generator():
    yield {
        "type": "user",
        "message": {"role": "user", "content": "First question"},
    }
    await asyncio.sleep(1)  # Can wait for conditions before yielding next
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "text", "text": "Follow-up with image"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}},
            ],
        },
    }

async for message in query(prompt=message_generator(), options=options):
    ...
```

```typescript
// TypeScript
async function* generateMessages() {
  yield { type: "user" as const, message: { role: "user" as const, content: "First question" } };
  // Optionally yield more messages dynamically
}

for await (const message of query({ prompt: generateMessages(), options })) { ... }
```

**Single message input** (plain string) does NOT support:
- Images attached to messages
- Dynamic message queuing / interruption
- Custom MCP tools (`mcpServers`)
- Hook integration
- `canUseTool` callback

---

## Message flow

With `include_partial_messages=True`:

```
StreamEvent (message_start)
StreamEvent (content_block_start) — text
StreamEvent (content_block_delta) — text chunks...
StreamEvent (content_block_stop)
StreamEvent (content_block_start) — tool_use
StreamEvent (content_block_delta) — tool input JSON chunks...
StreamEvent (content_block_stop)
StreamEvent (message_delta)
StreamEvent (message_stop)
AssistantMessage — complete assembled message
... tool executes ...
... more StreamEvents for next turn ...
ResultMessage — final result
```

---

## Build a streaming UI

```python
# Python — streaming UI with tool status indicators
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from claude_agent_sdk.types import StreamEvent
import sys

in_tool = False
async for message in query(
    prompt="Find all TODO comments",
    options=ClaudeAgentOptions(include_partial_messages=True, allowed_tools=["Read", "Grep"]),
):
    if isinstance(message, StreamEvent):
        event = message.event
        if event.get("type") == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                print(f"\n[Using {block.get('name')}...]", end="", flush=True)
                in_tool = True
        elif event.get("type") == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta" and not in_tool:
                sys.stdout.write(delta.get("text", ""))
                sys.stdout.flush()
        elif event.get("type") == "content_block_stop" and in_tool:
            print(" done")
            in_tool = False
    elif isinstance(message, ResultMessage):
        print("\n--- Complete ---")
```

---

## Limitations

- **Extended thinking**: when `max_thinking_tokens` / `maxThinkingTokens` is set, `StreamEvent` messages are NOT emitted
- **Structured output**: JSON result appears only in final `ResultMessage.structured_output`, not as streaming deltas
