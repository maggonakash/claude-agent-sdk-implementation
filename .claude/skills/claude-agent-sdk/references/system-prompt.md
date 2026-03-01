# System Prompt, CLAUDE.md & Skills

Customize Claude's behavior for SDK applications.

## Table of Contents
- [Default behavior](#default-behavior)
- [Method 1: CLAUDE.md files](#method-1-claudemd-files)
- [Method 2: systemPrompt with append](#method-2-systemprompt-with-append)
- [Method 3: Custom system prompt](#method-3-custom-system-prompt)
- [Method 4: Output styles](#method-4-output-styles)
- [Comparison](#comparison)
- [Using Skills in the SDK](#using-skills-in-the-sdk)

---

## Default behavior

By default the SDK uses a **minimal system prompt** — only essential tool instructions, no Claude Code coding guidelines or project context.

To get the full Claude Code system prompt behavior:
```python
options = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code"}
)
```

---

## Method 1: CLAUDE.md files

Project-specific instructions in `CLAUDE.md` or `.claude/CLAUDE.md`. Loaded only when `setting_sources` includes `"project"`.

```python
# Python — requires setting_sources to load CLAUDE.md
options = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code"},
    setting_sources=["project"],  # Required to load CLAUDE.md
)
```

```typescript
// TypeScript
const options = {
  systemPrompt: { type: "preset", preset: "claude_code" },
  settingSources: ["project"],  // Required to load CLAUDE.md
};
```

**CLAUDE.md example:**
```markdown
# Project Guidelines

## Code Style
- Use TypeScript strict mode
- Prefer functional components in React

## Commands
- Build: `npm run build`
- Test: `npm test`
```

> **Important:** `claude_code` preset does NOT automatically load CLAUDE.md — you must also set `setting_sources`.

**User-level** `~/.claude/CLAUDE.md` (global across all projects):
```python
setting_sources=["user", "project"]
```

---

## Method 2: systemPrompt with append

Add custom instructions while keeping Claude Code's full capabilities.

```python
# Python
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "Always include docstrings and type hints in Python code.",
    }
)
```

```typescript
// TypeScript
const options = {
  systemPrompt: {
    type: "preset",
    preset: "claude_code",
    append: "Always include docstrings and type hints in Python code."
  }
};
```

---

## Method 3: Custom system prompt

Complete control — replace the default entirely. Note: default tools, safety instructions, and environment context are lost unless you add them manually.

```python
# Python
options = ClaudeAgentOptions(
    system_prompt="""You are a Python coding specialist.
Follow these guidelines:
- Write clean, well-documented code
- Use type hints for all functions
- Prefer functional programming patterns"""
)
```

```typescript
// TypeScript
const options = {
  systemPrompt: "You are a Python coding specialist. Always use type hints."
};
```

---

## Method 4: Output styles

Saved markdown files that modify the system prompt persistently. Stored in `~/.claude/output-styles/` (user) or `.claude/output-styles/` (project).

```python
# Python — create an output style file
from pathlib import Path

style_dir = Path.home() / ".claude" / "output-styles"
style_dir.mkdir(parents=True, exist_ok=True)

(style_dir / "code-reviewer.md").write_text("""---
name: Code Reviewer
description: Thorough code review assistant
---

You are an expert code reviewer.
For every submission: check for bugs, evaluate performance, suggest improvements.""")
```

Activate via: `/output-style Code Reviewer` in CLI, or by including `setting_sources: ['user']` in SDK.

---

## Comparison

| Method | Persistence | Reusability | Tools preserved | Customization level |
|:-------|:-----------|:------------|:----------------|:--------------------|
| CLAUDE.md | Per-project file | Per-project | ✅ | Additions only |
| Output styles | Saved files | Across projects | ✅ | Replace default |
| `append` | Session only | In code | ✅ | Additions only |
| Custom string | Session only | In code | ❌ (must add manually) | Complete |

---

## Using Skills in the SDK

Skills are `SKILL.md` files in `.claude/skills/` that Claude invokes automatically. They must be on the filesystem and require explicit `setting_sources` configuration.

```python
# Python — enable Skills
options = ClaudeAgentOptions(
    cwd="/path/to/project",                     # Project with .claude/skills/
    setting_sources=["user", "project"],        # Required to load Skills
    allowed_tools=["Skill", "Read", "Write"],   # Include "Skill" tool
)
```

```typescript
// TypeScript
const options = {
  cwd: "/path/to/project",
  settingSources: ["user", "project"],
  allowedTools: ["Skill", "Read", "Write"],
};
```

**Skill locations:**
- Project: `.claude/skills/<skill-name>/SKILL.md` (shared via git)
- User: `~/.claude/skills/<skill-name>/SKILL.md` (personal, across projects)

**Verify Skills are available:**
```bash
ls .claude/skills/*/SKILL.md
ls ~/.claude/skills/*/SKILL.md
```

**Discover available Skills at runtime:**
```python
async for message in query(
    prompt="What Skills are available?",
    options=ClaudeAgentOptions(setting_sources=["user", "project"], allowed_tools=["Skill"])
):
    print(message)
```

> **Note:** The `allowed-tools` frontmatter field in SKILL.md only works with Claude Code CLI, NOT with the SDK. Control tool access via the main `allowedTools` option in your SDK configuration.
