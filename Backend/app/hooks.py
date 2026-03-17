"""
PreToolUse hooks for safety enforcement.

1. block_deletions    — prevents all file deletion operations
2. enforce_file_isolation — restricts writes to the session's output directory
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns that indicate a destructive Bash command
# ---------------------------------------------------------------------------
DESTRUCTIVE_PATTERNS = re.compile(
    r"""
    \brm\b          |   # rm / rm -rf
    \bunlink\b      |   # unlink
    \brmdir\b       |   # rmdir
    \bshutil\.rmtree\b |  # Python inline: shutil.rmtree(...)
    \bos\.remove\b  |   # Python inline: os.remove(...)
    \bos\.unlink\b  |   # Python inline: os.unlink(...)
    \bdel\b         |   # Windows-style del (unlikely but safe to block)
    \btrash\b           # trash-cli or similar
    """,
    re.VERBOSE | re.IGNORECASE,
)

DENY_REASON_BASH = (
    "BLOCKED: This Bash command contains a destructive operation. "
    "You are strictly prohibited from deleting any files. "
    "You may only read, copy, edit, and create files."
)

DENY_REASON_EMPTY_WRITE = (
    "BLOCKED: Writing empty content to an existing file is not allowed "
    "as it is equivalent to deleting the file's contents. "
    "You may only read, copy, edit, and create files."
)


# ---------------------------------------------------------------------------
# Hook: block destructive operations
# ---------------------------------------------------------------------------
async def block_deletions(input_data: dict, tool_use_id: str | None, context) -> dict:
    """PreToolUse hook that inspects Bash and Write calls for delete intent."""
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        hook_event = input_data.get("hook_event_name", "PreToolUse")

        if not isinstance(tool_input, dict):
            return {}

        # Guard 1: Bash commands containing destructive keywords
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if isinstance(command, str) and DESTRUCTIVE_PATTERNS.search(command):
                logger.warning(f"Blocked destructive Bash command: {command}")
                return {
                    "hookSpecificOutput": {
                        "hookEventName": hook_event,
                        "permissionDecision": "deny",
                        "permissionDecisionReason": DENY_REASON_BASH,
                    }
                }

        # Guard 2: Write tool with empty content (stealth delete)
        if tool_name == "Write":
            content = tool_input.get("content", "")
            file_path = tool_input.get("path", "") or tool_input.get("file_path", "")
            if file_path and isinstance(content, str) and content.strip() == "":
                logger.warning(f"Blocked empty write to file: {file_path}")
                return {
                    "hookSpecificOutput": {
                        "hookEventName": hook_event,
                        "permissionDecision": "deny",
                        "permissionDecisionReason": DENY_REASON_EMPTY_WRITE,
                    }
                }

        return {}

    except Exception as e:
        logger.error(f"Error in block_deletions hook: {e}", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Hook: enforce file isolation per session
# ---------------------------------------------------------------------------
async def enforce_file_isolation(
    input_data: dict,
    tool_use_id: str | None,
    context,
    *,
    allowed_write_dir: str,
    allowed_read_dirs: list[str],
) -> dict:
    """
    PreToolUse hook that ensures the agent only writes to its session directory
    and only reads from allowed directories (uploads + own session dir).

    This is called via a closure in agent.py that injects the session-specific paths.
    """
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        hook_event = input_data.get("hook_event_name", "PreToolUse")

        if not isinstance(tool_input, dict):
            return {}

        # Resolve the allowed directories for comparison
        allowed_write = os.path.realpath(allowed_write_dir)
        allowed_reads = [os.path.realpath(d) for d in allowed_read_dirs]

        def _is_under(path: str, directory: str) -> bool:
            """Check if path is under directory (resolved, no symlink tricks)."""
            real = os.path.realpath(path)
            return real.startswith(directory + os.sep) or real == directory

        def _is_readable(path: str) -> bool:
            return any(_is_under(path, d) for d in allowed_reads)

        def _is_writable(path: str) -> bool:
            return _is_under(path, allowed_write)

        # --- Write / Edit: must target the session output dir ----------------
        if tool_name in ("Write", "Edit"):
            file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
            if file_path and not _is_writable(file_path):
                logger.warning(
                    f"Blocked {tool_name} outside session dir: {file_path}"
                )
                return {
                    "hookSpecificOutput": {
                        "hookEventName": hook_event,
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"BLOCKED: You can only write files inside your "
                            f"session directory: {allowed_write_dir}. "
                            f"Attempted path: {file_path}"
                        ),
                    }
                }

        # --- Bash: check for redirects / writes outside session dir ----------
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if isinstance(command, str):
                # Check for output redirection to files outside session dir
                # This is a best-effort heuristic — the system prompt is
                # the primary enforcement, this hook catches obvious cases
                redirect_match = re.findall(r'>\s*([^\s;|&]+)', command)
                for target in redirect_match:
                    if not _is_writable(target):
                        logger.warning(
                            f"Blocked Bash redirect outside session dir: {target}"
                        )
                        return {
                            "hookSpecificOutput": {
                                "hookEventName": hook_event,
                                "permissionDecision": "deny",
                                "permissionDecisionReason": (
                                    f"BLOCKED: Bash output redirection must target "
                                    f"your session directory: {allowed_write_dir}. "
                                    f"Attempted target: {target}"
                                ),
                            }
                        }

        return {}

    except Exception as e:
        logger.error(f"Error in enforce_file_isolation hook: {e}", exc_info=True)
        return {}
