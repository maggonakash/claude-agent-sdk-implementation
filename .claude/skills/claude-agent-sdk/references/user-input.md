# User Approvals & Clarifying Questions

Surface Claude's permission requests and questions to users at runtime.

## Table of Contents
- [Overview](#overview)
- [canUseTool callback](#canusetool-callback)
- [Response types](#response-types)
- [Handle clarifying questions (AskUserQuestion)](#handle-clarifying-questions)
- [Important Python note](#important-python-note)

---

## Overview

Claude requests user input in two situations:
1. **Permission to use a tool** (e.g., delete files, run shell commands)
2. **Clarifying questions** via the `AskUserQuestion` tool

Both trigger your `canUseTool` callback, which **pauses agent execution** until you return a response.

> **Alternative:** To auto-allow/deny tools without user interaction, use [hooks](hooks.md) instead — they run before `canUseTool`.

---

## canUseTool callback

```python
# Python
from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

async def can_use_tool(tool_name: str, input_data: dict, context: ToolPermissionContext):
    print(f"Tool requested: {tool_name}")
    if tool_name == "Bash":
        print(f"Command: {input_data.get('command')}")

    response = input("Allow? (y/n): ")
    if response.lower() == "y":
        return PermissionResultAllow(updated_input=input_data)
    return PermissionResultDeny(message="User denied this action")

options = ClaudeAgentOptions(can_use_tool=can_use_tool)
```

```typescript
// TypeScript
const options = {
  canUseTool: async (toolName: string, input: any) => {
    console.log(`Tool: ${toolName}`);
    const approved = await askUser("Allow this action? (y/n)");
    if (approved) return { behavior: "allow", updatedInput: input };
    return { behavior: "deny", message: "User denied this action" };
  }
};
```

---

## Response types

| Action | Python | TypeScript |
|:-------|:-------|:-----------|
| Allow as-is | `PermissionResultAllow(updated_input=input_data)` | `{ behavior: "allow", updatedInput: input }` |
| Allow with modified input | `PermissionResultAllow(updated_input={...modified})` | `{ behavior: "allow", updatedInput: modifiedInput }` |
| Deny | `PermissionResultDeny(message="Reason...")` | `{ behavior: "deny", message: "Reason..." }` |

**Approve with modifications** (e.g., sandbox paths):
```python
async def can_use_tool(tool_name, input_data, context):
    if tool_name == "Bash":
        sandboxed = {**input_data, "command": input_data["command"].replace("/tmp", "/tmp/sandbox")}
        return PermissionResultAllow(updated_input=sandboxed)
    return PermissionResultAllow(updated_input=input_data)
```

**Suggest alternative** (deny with guidance):
```python
async def can_use_tool(tool_name, input_data, context):
    if tool_name == "Bash" and "rm" in input_data.get("command", ""):
        return PermissionResultDeny(
            message="Don't delete files. Compress them into an archive instead."
        )
    return PermissionResultAllow(updated_input=input_data)
```

---

## Handle clarifying questions

When `tool_name == "AskUserQuestion"`, Claude is asking for input — not requesting a tool. The `input_data` contains structured questions with multiple-choice options.

**Input structure:**
```json
{
  "questions": [
    {
      "question": "How should I format the output?",
      "header": "Format",
      "options": [
        { "label": "Summary", "description": "Brief overview" },
        { "label": "Detailed", "description": "Full explanation" }
      ],
      "multiSelect": false
    }
  ]
}
```

**Handle and return answers:**
```python
async def can_use_tool(tool_name, input_data, context):
    if tool_name == "AskUserQuestion":
        answers = {}
        for q in input_data.get("questions", []):
            print(f"\n{q['header']}: {q['question']}")
            for i, opt in enumerate(q["options"]):
                print(f"  {i+1}. {opt['label']} - {opt['description']}")
            response = input("Your choice: ").strip()
            # Map number to label, or use raw text for free-form input
            try:
                idx = int(response) - 1
                answers[q["question"]] = q["options"][idx]["label"]
            except (ValueError, IndexError):
                answers[q["question"]] = response  # Free text

        return PermissionResultAllow(
            updated_input={"questions": input_data["questions"], "answers": answers}
        )
    # Handle other tools
    return PermissionResultAllow(updated_input=input_data)
```

**Answer format:**
- Key: `question` field text (e.g., `"How should I format the output?"`)
- Value: selected option's `label` (e.g., `"Summary"`)
- Multi-select: join labels with `", "` (e.g., `"Introduction, Conclusion"`)
- Free text: use the user's raw input as the value

**Enable `AskUserQuestion`** — if you restrict `tools`, include it explicitly:
```python
options = ClaudeAgentOptions(
    tools=["Read", "Glob", "Grep", "AskUserQuestion"],  # Include AskUserQuestion!
    can_use_tool=can_use_tool,
)
```

`AskUserQuestion` is especially common in `plan` permission mode — Claude gathers requirements before proposing changes.

---

## Important Python note

In Python, `can_use_tool` requires **streaming input mode** AND a `PreToolUse` hook returning `{"continue_": True}` to keep the stream open:

```python
from claude_agent_sdk.types import HookMatcher

async def dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}

async def prompt_stream():
    yield {"type": "user", "message": {"role": "user", "content": "Create and delete a test file"}}

async for message in query(
    prompt=prompt_stream(),                             # Streaming input required
    options=ClaudeAgentOptions(
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]},  # Required
    ),
):
    ...
```

> Without the dummy `PreToolUse` hook, the stream closes before `can_use_tool` can be invoked.
