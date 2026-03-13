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

from app.hooks import block_deletions, enforce_file_isolation
from app.session_store import (
    add_history_entry,
    create_session,
    generate_session_id,
    get_history,
    get_session,
    session_exists,
    update_session,
)
from app.core.config import settings
from app.tracing import AgentTracer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fix: Allow running locally inside a Claude Code terminal session.
# ---------------------------------------------------------------------------
if "CLAUDECODE" in os.environ:
    del os.environ["CLAUDECODE"]

# ---------------------------------------------------------------------------
# Constants & path helpers
# ---------------------------------------------------------------------------

def get_session_paths(session_id: str) -> tuple[Path, Path, Path]:
    """Return (session_root, uploads_dir, processed_dir) for a session."""
    session_root = settings.WORKSPACE_DIR / session_id
    return session_root, session_root / "uploads", session_root / "processed"


def ensure_session_dirs(session_id: str) -> tuple[Path, Path, Path]:
    """Create and return the session directory structure."""
    session_root, uploads_dir, processed_dir = get_session_paths(session_id)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    return session_root, uploads_dir, processed_dir


# Relative paths — the agent's cwd is session_root, so ./uploads and
# ./processed just work without leaking absolute filesystem structure.
SYSTEM_PROMPT_APPEND = """
You are a document processing agent.

Your working directory is the session root.
Uploaded files (read-only source documents) are in: ./uploads
Your output directory for processed results is: ./processed

RULES:
- You MUST NEVER delete any files. Only read, copy, edit, and create.
- When editing a document, always make a copy first and edit the copy.
- Save ALL outputs to your processed output directory: ./processed
- You may READ files from the uploads directory but NEVER write there.
- Use the available Skills to read .pptx, .docx, and .xlsx files.
- Be thorough and report what you did after completing a task.
""".strip()

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

    uploads_dir = session_root / "uploads"
    processed_dir = session_root / "processed"

    # Build the system prompt with optional history context
    append_parts = [SYSTEM_PROMPT_APPEND]

    # List all currently uploaded files so the agent knows what's available
    # without needing to Glob first — saves a turn.
    if uploads_dir.exists():
        uploaded = [f.name for f in uploads_dir.iterdir() if f.is_file()]
        if uploaded:
            files_list = "\n".join(f"  - {name}" for name in uploaded)
            append_parts.append(f"Currently uploaded files in ./uploads:\n{files_list}")

    if history:
        history_text = _format_history(history)
        append_parts.append(HISTORY_PREAMBLE.format(history_text=history_text))

    append_text = "\n\n".join(append_parts)

    # Create a closure that captures the allowed paths for this session
    async def session_file_isolation(input_data, tool_use_id, context):
        return await enforce_file_isolation(
            input_data, tool_use_id, context,
            allowed_write_dir=str(processed_dir),
            allowed_read_dirs=[str(uploads_dir), str(processed_dir)],
        )

    opts = ClaudeAgentOptions(
        # Working directory is the session root
        cwd=str(session_root),

        # Full Claude Code system prompt + our custom rules appended
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": append_text,
        },

        # Load Skills from .claude/skills/ (user and project level)
        setting_sources=["user", "project"],

        # Autonomous — no human-in-the-loop permission prompts
        permission_mode="bypassPermissions",

        # Tools the agent can use
        allowed_tools=[
            "Skill",    # Invoke Skills for document parsing
            "Read",     # Read file contents
            "Write",    # Create new files
            "Edit",     # Edit existing files
            "Bash",     # Run shell commands (copying files, etc.)
            "Glob",     # Find files by pattern
            "Grep",     # Search file contents
            "WebSearch",
        ],

        # Safety hooks: deletion prevention + file isolation
        # hooks={
        #     "PreToolUse": [
        #         HookMatcher(matcher="Bash|Write|Edit", hooks=[
        #             block_deletions,
        #             session_file_isolation,
        #         ]),
        #     ],
        # },

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
) -> AsyncGenerator[AgentEvent, None]:
    """
    Execute an agent query and yield AgentEvent objects in real-time.

    Each event represents a meaningful status update that can be sent
    to the client as a Server-Sent Event.
    """

    # --- 1. Session setup (same as run_agent) --------------------------------
    is_new = True if session_id is None else not await session_exists(session_id)

    if session_id is None:
        session_id = generate_session_id()
        logger.info(f"Stream: Generated new session_id: {session_id}")

    if is_new:
        await create_session(session_id)
        sdk_session_id = None
        history = []
        logger.info(f"Stream: Created new session record for {session_id}")
    else:
        session_data = await get_session(session_id)
        sdk_session_id = session_data.get("sdk_session_id")
        history = session_data.get("history", [])
        logger.info(f"Stream: Resuming session {session_id} (SDK ID: {sdk_session_id}) with {len(history)} history items")

    session_root, _, processed_dir = ensure_session_dirs(session_id)

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
    
    logger.info(f"Stream: Built options for session {session_id}. History passed: {bool(options.system_prompt.get('append'))}")
    logger.info(f"Stream: System prompt append:\n{options.system_prompt.get('append')}")
    logger.info(f"Stream: User instruction:\n{instruction}")

    await add_history_entry(session_id, role="user", content=instruction)

    # --- MLflow trace ---
    tracer = AgentTracer()
    tracer.start(
        session_id=session_id,
        instruction=instruction,
        is_resume=not is_new,
        uploaded_files=uploaded_files,
    )

    # Emit the session_id immediately so the client knows which session to poll
    yield AgentEvent("session_start", {"session_id": session_id})

    captured_sdk_session_id: str = sdk_session_id or ""
    result_text: str = ""
    is_error: bool = False
    error_detail: str = ""
    final_cost_usd: float | None = None

    # Track streaming state for tool events
    current_tool_name: str | None = None
    current_tool_input: str = ""
    turn_count: int = 0

    try:
        async for message in query(prompt=prompt, options=options):

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
                        tracer.start_tool(current_tool_name)
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
                    tracer.end_tool(
                        current_tool_name,
                        summary=tool_summary,
                        tool_input=current_tool_input,
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
                tracer.record_turn(turn_count)
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
                final_cost_usd = message.total_cost_usd

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
        tracer.end(error="client_disconnected", result=result_text, turns=turn_count)
        # We record the partial result but don't mark it as a hard error in the system
        role = "assistant"
        content = f"[STREAM INTERRUPTED]\n{result_text}"
        await add_history_entry(session_id, role=role, content=content)
        raise  # Re-raise so FastAPI knows the connection was cleanly closed


    except Exception as e:
        is_error = True
        error_detail = str(e)
        tracer.end(error=str(e), result=result_text, turns=turn_count)
        await add_history_entry(session_id, role="error", content=str(e))
        yield AgentEvent("error", {
            "message": f"Exception: {error_detail}",
            "session_id": session_id,
        })

        if sdk_session_id:
            logger.error(f"Failed to resume session {session_id}: {e}")
        return  # Stop the generator

    # --- End trace & persist results ---
    tracer.end(
        result=result_text,
        turns=turn_count,
        cost_usd=final_cost_usd,
        error=error_detail if is_error else None,
    )

    role = "error" if is_error else "assistant"
    content = f"[ERROR] {error_detail}\n{result_text}" if is_error else result_text
    await add_history_entry(session_id, role=role, content=content)

    await update_session(
        session_id,
        sdk_session_id=captured_sdk_session_id,
    )

    # Emit file list
    files_modified = []
    if processed_dir.exists():
        files_modified = [str(p) for p in processed_dir.rglob("*") if p.is_file()]

    yield AgentEvent("files", {
        "files_modified": files_modified,
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
        return cmd[:300]
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
        return str(data)[:200]
