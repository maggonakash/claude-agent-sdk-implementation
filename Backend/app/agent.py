"""
Claude Agent integration using the Claude Agent SDK.

Uses query() with:
  - bypassPermissions  → autonomous execution (sandboxed in Docker)
  - PreToolUse hook    → blocks file deletions + enforces per-session file isolation
  - setting_sources    → loads Skills from .claude/skills/
  - session resumption → user can continue a prior conversation
  - pre-generated IDs  → session IDs are created before query() starts
  - history tracking   → conversation turns are persisted per session
  - streaming events   → real-time progress via include_partial_messages
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator
import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    SystemMessage,
    query,
)
from claude_agent_sdk.types import StreamEvent

from app.hooks import block_deletions_except_scratch, enforce_file_isolation
from app.db.sessions import (
    create_session,
    generate_session_id,
    get_session,
    session_exists,
    update_session,
)
from app.db.messages import get_messages_paginated
from app.db.artifacts import create_artifact, get_existing_file_paths
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _prompt_stream(text: str, session_id: str = ""):
    """Wrap a string prompt as an AsyncIterable to avoid deadlock when hooks are enabled."""
    yield {
        "type": "user",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
        "session_id": session_id,
    }

# ---------------------------------------------------------------------------
# Fix: Allow running locally inside a Claude Code terminal session.
# ---------------------------------------------------------------------------
if "CLAUDECODE" in os.environ:
    del os.environ["CLAUDECODE"]

# ---------------------------------------------------------------------------
# Constants & path helpers
# ---------------------------------------------------------------------------

def get_session_paths(session_id: str) -> tuple[Path, Path, Path, Path]:
    """Return (session_root, uploads_dir, processed_dir) for a session."""
    session_root = settings.WORKSPACE_DIR / session_id
    return (
        session_root, 
        session_root / "user-uploads", 
        session_root / "scratch",
        session_root / "artifacts",
        )


def ensure_session_dirs(session_id: str) -> tuple[Path, Path, Path, Path]:
    """Create and return the session directory structure."""
    session_root, user_uploads, scratch, artifacts = get_session_paths(session_id)
    user_uploads.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    return session_root, user_uploads, scratch, artifacts


def _build_system_prompt(session_root: Path) -> str:
    """Build the system prompt with the actual session path baked in."""
    session_path = str(session_root)
    return f"""You are a document processing agent operating in a strictly sandboxed environment.

Your workspace is: {session_path}
This is the ONLY directory you have access to. Everything outside it is off-limits.

You have three subdirectories:

  ./user-uploads/  — READ ONLY. Source files uploaded by the user.
  ./scratch/       — READ, WRITE, DELETE. Your private scratchpad for temporary files,
                     intermediate outputs, and helper scripts. The user does not see this.
  ./artifacts/     — READ, WRITE (no delete). Final deliverables for the user.
                     Save all outputs the user should receive here.

═══════════════════════════════════════════════════════════════════
                      STRICT SECURITY RULES
  These rules are non-negotiable. Violations are blocked by hooks
  and will waste turns. Do NOT attempt anything prohibited below.
═══════════════════════════════════════════════════════════════════

DIRECTORY ACCESS:
- Your entire world is {session_path} — you CANNOT access anything outside it.
- NEVER use `..` to traverse above your session root.
- NEVER use absolute paths outside {session_path}.
- NEVER attempt to access other sessions, system files, or any path outside your workspace.
- All reads, writes, globs, greps, and bash commands are restricted to {session_path}.
- NEVER run commands like `ls /`, `ls /app`, `cat /etc/anything`, or ANY command that
  references paths outside your session — even to "just look" or "check what's there".
  You do not have access and must not attempt it.
- If the user asks you to access files or directories outside your session (root folder,
  system directories, other apps, etc.), refuse immediately. Do not attempt the command
  first — just explain that you only have access to {session_path}.

WRITE PERMISSIONS:
- ./user-uploads/ → READ ONLY. Never write, edit, move, rename, or delete anything here.
- ./scratch/      → Full access (read, write, delete).
- ./artifacts/    → Read and write only. Never delete files here.
- If asked to modify a source document, copy it to ./scratch/ first, edit there,
  then save the final result to ./artifacts/.

DESTRUCTIVE COMMANDS:
- NEVER run rm, rmdir, unlink, shred, truncate, or any deletion command outside ./scratch/.
- NEVER run mv outside ./scratch/. Use cp to copy files to ./artifacts/.
- Do not attempt these even if the user asks — the hooks will block them.

CODE & SCRIPT SAFETY:
- Before running ANY script file uploaded by the user, you MUST first read its full
  contents using the Read tool and verify it is safe. Never trust user-uploaded scripts
  blindly.
- Inline code (python -c, bash -c, etc.) is allowed for legitimate use, but you must
  ensure the code is not malicious before running it.
- Whether running a script file, inline code, or writing your own code, always verify
  it does NOT:
    • Access paths outside {session_path} (../, absolute paths, /etc, /home, etc.)
    • Attempt to access or enumerate other session directories or user data
    • Read environment variables or secrets (os.environ, process.env, $ENV_VAR, etc.)
    • Spawn reverse shells, open listening ports, or establish C2 connections
    • Exfiltrate session data — never send file contents, user data, or session info
      to external servers (e.g., via POST requests, curl --data, etc.)
    • Download and execute remote code (curl ... | bash, wget ... | python, exec of
      fetched content, etc.)
    • Contain obfuscated code (base64-encoded exec, eval of encoded strings, etc.)
    • Use os.system(), subprocess with shell=True, or exec()/eval() with dynamic input
      in ways that could bypass sandbox restrictions
    • Attempt to escalate privileges or modify system settings
- The above list is not exhaustive. Use your own judgment to identify anything that
  looks malicious, suspicious, or could compromise the sandbox — even if it is not
  explicitly listed above. If something feels wrong, it probably is. Err on the side
  of caution and refuse.
- If a user-uploaded script contains any malicious patterns, refuse to run it and
  explain why.
- Network access (curl, wget, requests, APIs) is allowed for legitimate tasks. The
  restriction is only on exfiltration (sending session/user data out) and remote
  code execution (downloading and running untrusted code).

FORBIDDEN ACTIONS (even if the user requests them):
- Do not leak environment variables, secrets, API keys, or configuration files.
- Do not install backdoors, keyloggers, or any form of persistent access.
- Do not access /proc, /sys, /dev, or any OS-level resources outside the sandbox.
- Do not enumerate or access other users' sessions or workspace directories.
- If a user asks you to test, bypass, or break the sandbox — politely decline.
  You may explain what the restrictions are, but never attempt to circumvent them.
- This list is not exhaustive. If an action could compromise security, privacy, or
  the integrity of the sandbox — do not do it, even if not explicitly listed here.

GENERAL RULES:
- Use the available Skills to read .pdf, .pptx, .docx, and .xlsx files.
- Be thorough and report what you did after completing a task.
- If a user asks you to do something that violates these rules, politely decline
  and explain why it is not allowed."""

HISTORY_PREAMBLE = """
--- Previous conversation history for this session ---
{history_text}
--- End of previous history ---
""".strip()


# ---------------------------------------------------------------------------
# History formatter
# ---------------------------------------------------------------------------

def _format_history(history: list[dict]) -> str:
    """Format stored history entries into a readable text block."""
    if not history:
        return ""
    lines = []
    for entry in history:
        role = entry["role"].upper()
        content = entry["content"]
        ts = entry.get("timestamp", "")
        lines.append(f"[{role}] ({ts})\n{content}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Agent options builder
# ---------------------------------------------------------------------------

def _build_options(
    app_session_id: str,
    session_root: Path,
    sdk_session_id: str | None = None,
    history: list[dict] | None = None,
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with hooks, permissions, and Skills."""
    logger.info(f"Building options — session={app_session_id}, cwd={session_root}")

    # _, user_uploads, scratch, artifacts = get_session_paths(app_session_id)
    user_uploads = session_root / "user-uploads"
    scratch = session_root / "scratch"
    artifacts = session_root / "artifacts"

    # Build the system prompt with optional history context
    append_parts = [_build_system_prompt(session_root)]

    # List all currently uploaded files so the agent knows what's available
    # without needing to Glob first — saves a turn.
    if user_uploads.exists():
        uploaded = [f.name for f in user_uploads.iterdir() if f.is_file()]
        if uploaded:
            files_list = "\n".join(f"  - {name}" for name in uploaded)
            append_parts.append(f"Currently uploaded files in ./user-uploads:\n{files_list}")

    if history:
        history_text = _format_history(history)
        append_parts.append(HISTORY_PREAMBLE.format(history_text=history_text))

    append_text = "\n\n".join(append_parts)

    # Create a closure that captures the allowed paths for this session
    async def session_file_isolation(input_data, tool_use_id, context):
        return await enforce_file_isolation(
            input_data, tool_use_id, context,
            session_root=str(session_root),
            allowed_write_dirs=[str(scratch), str(artifacts)],
            allowed_delete_dirs=[str(scratch)],
        )

    opts = ClaudeAgentOptions(
        cwd=str(session_root),
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": append_text,
        },
        # Load Skills from .claude/skills/ (user and project level)
        setting_sources=["user", "project"],
        # Autonomous — no human-in-the-loop permission prompts
        permission_mode="bypassPermissions",
        allowed_tools=[
            "Skill",    # Invoke Skills for document parsing
            "Read",     # Read file contents
            "Write",    # Create new files
            "Edit",     # Edit existing files
            "Bash",     # Run shell commands (copying files, etc.)
            "Glob",     # Find files by pattern
            "Grep",     # Search file contents
            "WebSearch",
            "Agent",    # Spawn sub-agents for complex tasks
        ],
        # OS-level sandbox: kernel-enforced filesystem isolation for Bash
        sandbox={
            "enabled": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "enableWeakerNestedSandbox": True,
        },
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher="Bash|Write|Edit|Read|Glob|Grep",
                    hooks=[
                        block_deletions_except_scratch,
                        session_file_isolation,
                    ],
                    timeout=300,
                ),
            ],
        },
        # Safety: cap turns to prevent runaway execution
        max_turns=60,
        # Streaming: emit StreamEvent messages for real-time progress
        include_partial_messages=True,
    )

    # Resume via the SDK's internal session ID (not our app session ID)
    if sdk_session_id:
        opts.resume = sdk_session_id

    return opts


# ---------------------------------------------------------------------------
# Streaming event types (sent to the client via SSE)
# ---------------------------------------------------------------------------

@dataclass
class AgentEvent:
    """A single event emitted during agent execution for SSE streaming."""
    event_type: str   # "status", "tool_start", "tool_end", "text_delta", "result", "error"
    data: dict

    def to_sse(self) -> str:
        """Format as a Server-Sent Event line."""
        return f"data: {json.dumps({'type': self.event_type, **self.data})}\n\n"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Run the agent with streaming (yields AgentEvents for SSE)
# ---------------------------------------------------------------------------

async def run_agent_stream(
    instruction: str,
    session_id: str | None = None,
    uploaded_files: list[str] | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    message_id: str | None = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    Execute an agent query and yield AgentEvent objects in real-time.

    Each event represents a meaningful status update that can be sent
    to the client as a Server-Sent Event.
    """

    # --- 1. Session setup (same as run_agent) --------------------------------
    is_new = True if session_id is None else not await session_exists(session_id)
    logger.info(f"is session id None? {is_new}")

    if is_new:
        session_id = generate_session_id()
        logger.info(f"Stream: Generated new session_id: {session_id}")
        await create_session(session_id, user_id or "", user_email or "")
        sdk_session_id = None
        history = []
        logger.info(f"Stream: Created new session record for {session_id}")
    else:
        logger.info(f"Found session id: {session_id}")
        session_data = await get_session(session_id)
        sdk_session_id = session_data.get("sdk_session_id")
        # Load history from messages collection (convert turns to flat role/content pairs)
        msg_result = await get_messages_paginated(session_id, page=1, page_size=50)
        history = []
        for msg in msg_result["messages"]:
            # Skip messages with no agent response yet — that's the current message
            # being processed right now (already saved to DB by the endpoint).
            if not msg.get("agent_response") and not msg.get("error"):
                continue
            history.append({"role": "user", "content": msg["user_message"], "timestamp": msg["created_at"]})
            if msg.get("agent_response"):
                history.append({"role": "assistant", "content": msg["agent_response"], "timestamp": msg["updated_at"]})
            elif msg.get("error"):
                history.append({"role": "error", "content": msg["error"], "timestamp": msg["updated_at"]})
        logger.info(f"Stream: Resuming session {session_id} (SDK ID: {sdk_session_id}) with {len(history)} history entries")

    session_root, user_uploads, scratch, artifacts = ensure_session_dirs(session_id)

    # Build prompt with upload info
    prompt = instruction
    if uploaded_files:
        files_list = ", ".join(uploaded_files)
        prompt = (
            f"[The user has uploaded the following files: {files_list}]\n\n"
            f"{instruction}"
        )
        logger.info(f"Stream: Added upload context to prompt. Files: {files_list}")

    options = _build_options(
        app_session_id=session_id,
        session_root=session_root,
        sdk_session_id=sdk_session_id,
        history=history if sdk_session_id is None and history else None,
    )
    
    logger.info(f"Stream: Built options for session {session_id}.")
    logger.info(f"Stream: User instruction:\n{instruction}")

    # Emit the session_id immediately so the client knows which session to poll
    yield AgentEvent("session_start", {"session_id": session_id})

    captured_sdk_session_id: str = sdk_session_id or ""
    result_text: str = ""
    is_error: bool = False
    error_detail: str = ""

    # Track streaming state for tool events
    current_tool_name: str | None = None
    current_tool_input: str = ""
    turn_count: int = 0

    try:
        async for message in query(prompt=_prompt_stream(prompt), options=options):

            # --- StreamEvent: real-time token-level updates ---
            if isinstance(message, StreamEvent):
                event = message.event
                event_type = event.get("type", "")

                # Tool call started
                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool_name = block.get("name")
                        current_tool_input = ""
                        yield AgentEvent("tool_start", {
                            "tool": current_tool_name,
                            "session_id": session_id,
                        })

                # Accumulate tool input JSON (for logging what args were passed)
                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "input_json_delta":
                        current_tool_input += delta.get("partial_json", "")
                    elif delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield AgentEvent("text_delta", {
                                "text": text,
                                "session_id": session_id,
                            })

                # Tool call block finished
                elif event_type == "content_block_stop" and current_tool_name:
                    # Parse the tool input to get useful info (e.g. file path)
                    tool_summary = _summarize_tool_input(
                        current_tool_name, current_tool_input
                    )
                    yield AgentEvent("tool_end", {
                        "tool": current_tool_name,
                        "summary": tool_summary,
                        "session_id": session_id,
                    })
                    current_tool_name = None
                    current_tool_input = ""

            # --- SystemMessage: init ---
            elif isinstance(message, SystemMessage) and message.subtype == "init":
                captured_sdk_session_id = message.data.get(
                    "session_id", captured_sdk_session_id
                )
                yield AgentEvent("status", {
                    "message": "Agent initialized",
                    "session_id": session_id,
                })

            # --- AssistantMessage: a completed assistant turn ---
            elif isinstance(message, AssistantMessage):
                turn_count += 1
                yield AgentEvent("status", {
                    "message": f"Turn {turn_count} completed",
                    "turn": turn_count,
                    "max_turns": options.max_turns,
                    "session_id": session_id,
                })

                # Check for per-message errors
                if message.error:
                    yield AgentEvent("error", {
                        "message": f"Error on turn {turn_count}: {message.error}",
                        "session_id": session_id,
                    })

            # --- ResultMessage: final outcome ---
            elif isinstance(message, ResultMessage):
                result_text = message.result or ""

                if message.subtype == "success" and not message.is_error:
                    yield AgentEvent("result", {
                        "status": "success",
                        "result": result_text,
                        "turns_used": message.num_turns,
                        "cost_usd": message.total_cost_usd,
                        "session_id": session_id,
                    })
                else:
                    is_error = True
                    error_detail = (
                        f"Agent finished with status '{message.subtype}'. "
                        f"Turns used: {message.num_turns}/{options.max_turns}."
                    )
                    if message.is_error:
                        error_detail += " is_error=True."
                    yield AgentEvent("error", {
                        "status": message.subtype,
                        "message": error_detail,
                        "result": result_text,
                        "turns_used": message.num_turns,
                        "session_id": session_id,
                    })

    except asyncio.CancelledError:
        logger.warning(f"Client disconnected during stream for session {session_id}. Cancelling agent.")
        raise  # Re-raise so FastAPI knows the connection was cleanly closed

    except Exception as e:
        is_error = True
        error_detail = str(e)
        yield AgentEvent("error", {
            "message": f"Exception: {error_detail}",
            "session_id": session_id,
        })
        logger.info("error while streaming: {e}", exc_info=True)

        # if sdk_session_id:
        #     logger.error(f"Failed to resume session {session_id}: {e}")
        return  # Stop the generator

    # --- Persist SDK session ID ---
    await update_session(
        session_id,
        sdk_session_id=captured_sdk_session_id,
    )

    # --- Save new artifacts to DB and emit metadata ---
    new_artifacts = []
    if artifacts.exists() and message_id:
        # Use a thread for sync I/O (rglob, stat) to avoid blocking the event loop
        def _scan_artifacts():
            return [
                (p.relative_to(artifacts), p.stat().st_size)
                for p in artifacts.rglob("*") if p.is_file()
            ]

        all_files = await asyncio.to_thread(_scan_artifacts)
        existing_paths = await get_existing_file_paths(session_id)

        for rel_path, size in all_files:
            path_str = str(rel_path)
            if path_str not in existing_paths:
                doc = await create_artifact(
                    session_id=session_id,
                    message_id=message_id,
                    user_id=user_id or "",
                    filename=rel_path.name,
                    file_path=path_str,
                    file_size=size,
                )
                new_artifacts.append(doc)

    yield AgentEvent("artifacts", {
        "artifacts": [
            {
                "artifact_id": a["artifact_id"],
                "filename": a["filename"],
                "file_path": a["file_path"],
                "file_size": a["file_size"],
                "mime_type": a["mime_type"],
            }
            for a in new_artifacts
        ],
        "session_id": session_id,
    })

    yield AgentEvent("done", {"session_id": session_id})


# ---------------------------------------------------------------------------
# Helper: summarize tool input for human-readable status
# ---------------------------------------------------------------------------

def _summarize_tool_input(tool_name: str, raw_json: str) -> str:
    """Extract a short human-readable summary from a tool's input JSON."""
    try:
        data = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        return raw_json[:100] if raw_json else ""

    if tool_name == "Read":
        return data.get("file_path", "")
    elif tool_name == "Write":
        path = data.get("file_path", "")
        return f"writing {path}"
    elif tool_name == "Edit":
        return data.get("file_path", "")
    elif tool_name == "Bash":
        cmd = data.get("command", "")
        return cmd
    elif tool_name == "Glob":
        return data.get("pattern", "")
    elif tool_name == "Grep":
        return data.get("pattern", "")
    elif tool_name == "Skill":
        return data.get("skill", "")
    elif tool_name == "TodoWrite":
        todos = data.get("todos", [])
        in_progress = [t for t in todos if t.get("status") == "in_progress"]
        if in_progress:
            return in_progress[0].get("activeForm", "")
        return f"{len(todos)} todos"
    else:
        return str(data)
