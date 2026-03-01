# Session Management & Permissions

## Table of Contents
- [Session management](#session-management)
  - [Get the session ID](#get-the-session-id)
  - [Resume a session](#resume-a-session)
  - [Fork a session](#fork-a-session)
- [Permission modes](#permission-modes)
  - [Set at query time](#set-at-query-time)
  - [Change dynamically](#change-dynamically)
- [Permission evaluation order](#permission-evaluation-order)

---

## Session management

### Get the session ID

The first message in any query is a `system` init message containing the `session_id`. Save it to resume later.

```python
# Python
session_id = None
async for message in query(prompt="Help me build a web app", options=ClaudeAgentOptions()):
    if hasattr(message, "subtype") and message.subtype == "init":
        session_id = message.data.get("session_id")
        print(f"Session: {session_id}")
```

```typescript
// TypeScript
let sessionId: string | undefined;
for await (const message of query({ prompt: "Help me build a web app" })) {
  if (message.type === "system" && message.subtype === "init") {
    sessionId = message.session_id;
  }
}
```

### Resume a session

Pass the saved `session_id` as `resume` to continue with full context from the previous session.

```python
# Python
async for message in query(
    prompt="Continue implementing the auth system",
    options=ClaudeAgentOptions(
        resume="session-xyz",
        model="claude-opus-4-6",
        allowed_tools=["Read", "Edit", "Write", "Bash"],
    ),
):
    print(message)
```

```typescript
// TypeScript
for await (const message of query({
  prompt: "Continue implementing the auth system",
  options: {
    resume: "session-xyz",
    model: "claude-opus-4-6",
    allowedTools: ["Read", "Edit", "Write", "Bash"],
  }
})) {
  console.log(message);
}
```

### Fork a session

Resume with `forkSession: true` (TypeScript) / `fork_session=True` (Python) to create a new branch without modifying the original.

| Behavior | `forkSession: false` (default) | `forkSession: true` |
|:---------|:-------------------------------|:--------------------|
| Session ID | Same as original | New ID generated |
| History | Appends to original | New branch from resume point |
| Original | Modified | Preserved unchanged |
| Use case | Linear continuation | Explore alternative approaches |

```python
# Python — fork for a different approach
async for message in query(
    prompt="Now try with GraphQL instead",
    options=ClaudeAgentOptions(
        resume=session_id,
        fork_session=True,
        model="claude-opus-4-6",
    ),
):
    if hasattr(message, "subtype") and message.subtype == "init":
        forked_id = message.data.get("session_id")  # New session ID
```

---

## Permission modes

### Available modes

| Mode | Description |
|:-----|:------------|
| `default` | Standard behavior; unmatched tools trigger `canUseTool` callback |
| `acceptEdits` | Auto-approve file edits + filesystem ops (`mkdir`, `rm`, `mv`, `cp`) |
| `bypassPermissions` | All tools auto-approved, no prompts (use with extreme caution) |
| `plan` | No tool execution; Claude plans only, can ask clarifying questions |

> **Warning:** `bypassPermissions` propagates to all subagents. Only use in controlled environments.

### Set at query time

```python
# Python
options = ClaudeAgentOptions(permission_mode="acceptEdits")
```

```typescript
// TypeScript
const options = { permissionMode: "acceptEdits" };
```

### Change dynamically

Switch permission mode mid-session using `set_permission_mode()` / `setPermissionMode()`. Useful to start restrictive and relax after reviewing initial output.

```python
# Python
q = query(
    prompt="Help me refactor the auth module",
    options=ClaudeAgentOptions(permission_mode="default"),
)
await q.set_permission_mode("acceptEdits")  # Relax after seeing Claude's plan

async for message in q:
    if hasattr(message, "result"):
        print(message.result)
```

```typescript
// TypeScript
const q = query({
  prompt: "Help me refactor the auth module",
  options: { permissionMode: "default" }
});

await q.setPermissionMode("acceptEdits");

for await (const message of q) {
  if ("result" in message) console.log(message.result);
}
```

---

## Permission evaluation order

When Claude requests a tool, the SDK checks in this order:

1. **Hooks** — run first; can allow, deny, or pass to next step
2. **Permission rules** — declarative allow/deny in `settings.json` (deny first, then allow, then ask)
3. **Permission mode** — active mode (`bypassPermissions`, `acceptEdits`, etc.)
4. **`canUseTool` callback** — your runtime approval callback

See [user-input.md](user-input.md) for the `canUseTool` callback.
See [hooks.md](hooks.md) for hook-based permission control.
