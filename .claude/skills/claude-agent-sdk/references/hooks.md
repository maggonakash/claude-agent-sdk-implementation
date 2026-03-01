# Hooks

Intercept and customize agent behavior at key execution points.

## Table of Contents
- [Overview](#overview)
- [Available hooks](#available-hooks)
- [Configure hooks](#configure-hooks)
- [Callback function signature](#callback-function-signature)
- [Hook outputs](#hook-outputs)
- [Common patterns](#common-patterns)

---

## Overview

Hooks are callbacks that run when agent events fire. Use them to:
- **Block** dangerous operations (e.g., writes to `.env`)
- **Modify** tool inputs before execution (e.g., redirect file paths)
- **Log/audit** every tool call
- **Auto-approve** specific tools
- **Send notifications** to Slack, webhooks, etc.

---

## Available hooks

| Hook Event | Python | TypeScript | Trigger |
|:-----------|:-------|:-----------|:--------|
| `PreToolUse` | ✅ | ✅ | Before a tool executes (can block or modify) |
| `PostToolUse` | ✅ | ✅ | After a tool completes |
| `PostToolUseFailure` | ✅ | ✅ | After a tool fails |
| `UserPromptSubmit` | ✅ | ✅ | User prompt submitted |
| `Stop` | ✅ | ✅ | Agent execution stops |
| `SubagentStart` | ✅ | ✅ | Subagent starts |
| `SubagentStop` | ✅ | ✅ | Subagent finishes |
| `Notification` | ✅ | ✅ | Agent status messages |
| `PreCompact` | ✅ | ✅ | Before conversation compaction |
| `PermissionRequest` | ✅ | ✅ | Permission dialog triggered |
| `SessionStart` | ❌ | ✅ | Session initializes |
| `SessionEnd` | ❌ | ✅ | Session terminates |

---

## Configure hooks

```python
# Python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, HookMatcher

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(matcher="Write|Edit", hooks=[my_callback])  # Regex filter
        ],
        "PostToolUse": [
            HookMatcher(hooks=[audit_logger])  # No matcher = fires for all tools
        ],
    }
)
```

```typescript
// TypeScript
const options = {
  hooks: {
    PreToolUse: [
      { matcher: "Write|Edit", hooks: [myCallback] },  // Regex filter
    ],
    PostToolUse: [
      { hooks: [auditLogger] }  // No matcher = fires for all tools
    ],
  }
};
```

**Matcher patterns:**
- `"Write|Edit"` — file modification tools
- `"Bash"` — shell commands
- `"^mcp__"` — all MCP tools
- No matcher — fires for every tool

---

## Callback function signature

```python
# Python
async def my_hook(input_data: dict, tool_use_id: str | None, context) -> dict:
    tool_name = input_data["tool_name"]          # e.g. "Write"
    tool_input = input_data["tool_input"]        # e.g. {"file_path": "...", "content": "..."}
    hook_event = input_data["hook_event_name"]   # e.g. "PreToolUse"
    session_id = input_data["session_id"]
    # ... your logic
    return {}  # Empty = allow operation unchanged
```

```typescript
// TypeScript
import { HookCallback, PreToolUseHookInput } from "@anthropic-ai/claude-agent-sdk";

const myHook: HookCallback = async (input, toolUseID, { signal }) => {
  const preInput = input as PreToolUseHookInput;
  const toolInput = preInput.tool_input as Record<string, unknown>;
  // ... your logic
  return {};
};
```

---

## Hook outputs

Return `{}` to allow unchanged. Otherwise use these fields:

### Block an operation
```python
return {
    "hookSpecificOutput": {
        "hookEventName": input_data["hook_event_name"],
        "permissionDecision": "deny",
        "permissionDecisionReason": "Not allowed",
    }
}
```

### Allow with input modification
```python
return {
    "hookSpecificOutput": {
        "hookEventName": input_data["hook_event_name"],
        "permissionDecision": "allow",    # Required when using updatedInput
        "updatedInput": {**input_data["tool_input"], "file_path": "/sandbox/new/path"},
    }
}
```

### Inject context into conversation
```python
return {
    "systemMessage": "Remember: /etc is protected.",
    "hookSpecificOutput": {
        "hookEventName": input_data["hook_event_name"],
        "permissionDecision": "deny",
        "permissionDecisionReason": "System dir off-limits",
    },
}
```

### Async (fire-and-forget for side effects)
```python
async def logging_hook(input_data, tool_use_id, context):
    asyncio.create_task(send_to_logging_service(input_data))
    return {"async_": True, "asyncTimeout": 30000}
```

> **Priority:** `deny` > `ask` > `allow` — if any hook returns deny, operation is blocked.

---

## Common patterns

### Block writes to .env
```python
async def protect_env_files(input_data, tool_use_id, context):
    file_path = input_data["tool_input"].get("file_path", "")
    if file_path.endswith(".env"):
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": "Cannot modify .env files",
            }
        }
    return {}

options = ClaudeAgentOptions(
    hooks={"PreToolUse": [HookMatcher(matcher="Write|Edit", hooks=[protect_env_files])]}
)
```

### Auto-approve read-only tools
```python
async def auto_approve_reads(input_data, tool_use_id, context):
    if input_data["tool_name"] in ["Read", "Glob", "Grep"]:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "allow",
            }
        }
    return {}
```

### Redirect writes to sandbox
```python
async def redirect_to_sandbox(input_data, tool_use_id, context):
    if input_data["tool_name"] == "Write":
        original = input_data["tool_input"].get("file_path", "")
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "allow",
                "updatedInput": {**input_data["tool_input"], "file_path": f"/sandbox{original}"},
            }
        }
    return {}
```

### Chain multiple hooks
```python
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(hooks=[rate_limiter]),       # First: rate limits
            HookMatcher(hooks=[auth_check]),          # Second: permissions
            HookMatcher(hooks=[input_sanitizer]),     # Third: sanitize
            HookMatcher(hooks=[audit_logger]),        # Last: log
        ]
    }
)
```

### Forward Notification to Slack
```python
async def notify_slack(input_data, tool_use_id, context):
    try:
        await asyncio.to_thread(send_slack, input_data.get("message", ""))
    except Exception as e:
        print(f"Slack notification failed: {e}")
    return {}

options = ClaudeAgentOptions(
    hooks={"Notification": [HookMatcher(hooks=[notify_slack])]}
)
```

### Troubleshooting
- Hook event names are **case-sensitive**: `PreToolUse` not `preToolUse`
- Matchers only filter by **tool name**, not file paths — check `tool_input.file_path` inside callback
- `SessionStart`/`SessionEnd` Python SDK callback hooks are not supported; use shell command hooks in `.claude/settings.json` instead
- When using `updatedInput`, you must also set `permissionDecision: "allow"`
