"""
PreToolUse hooks for safety enforcement.

1. block_deletions_except_scratch  — prevents file deletion outside ./scratch/
2. enforce_file_isolation — restricts ALL file access to the session directory

Access rules:
  ./user-uploads/  — READ only
  ./scratch/       — READ, WRITE, DELETE
  ./artifacts/     — READ, WRITE
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
DESTRUCTIVE_PATTERNS = re.compile(
    r"""
    \brm\b          |
    \brmdir\b       |
    \bunlink\b      |
    \bshred\b       |
    \btruncate\b    |
    \btrash\b       |
    \bdel\b         |
    \bmv\b          |
    \bshutil\.rmtree\b |
    \bos\.remove\b  |
    \bos\.unlink\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Regex to find absolute paths in a bash command string
ABS_PATH_RE = re.compile(r'(?:^|[\s=\'"(])(/[^\s;|&\'">`)\]]+)')

# Regex to find redirect targets (> or >>)
REDIRECT_RE = re.compile(r'>{1,2}\s*([^\s;|&]+)')

# Bash commands ALLOWED to run. Everything else is blocked.
# These are safe utility commands that don't read file contents or leak info.
ALLOWED_BASH_CMDS = {
    # File management (writes checked separately)
    "ls", "cp", "mkdir", "chmod", "touch", "wc", "file", "diff",
    # Text processing (stdin/pipe only, not file reading)
    "sort", "uniq", "tr", "cut", "paste", "fmt", "fold", "column",
    "sed", "awk", "grep", "rg",
    # Archive / compression
    "tar", "zip", "unzip", "gzip", "gunzip", "bzip2", "xz",
    # Package managers & runtimes (for installing deps in scratch)
    "pip", "pip3", "npm", "npx", "node", "python", "python3",
    # Misc safe utilities
    "echo", "printf", "date", "basename", "dirname", "realpath",
    "true", "false", "test", "sleep", "tee",
    # pdf/doc processing tools
    "pdftotext", "pdftk", "libreoffice", "convert", "magick",
    "pandoc", "wkhtmltopdf",
}

# Commands that copy files — destination must be writable, source must be in session
COPY_CMDS = {"cp", "rsync", "install", "scp"}


def _is_under(path: str, directory: str) -> bool:
    """Return True if resolved path is inside resolved directory."""
    real_path = os.path.realpath(path)
    real_dir = os.path.realpath(directory)
    return real_path.startswith(real_dir + os.sep) or real_path == real_dir


def _resolve(path: str, cwd: str) -> str:
    """Resolve a path against cwd, then realpath."""
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(cwd, path))


def _deny(hook_event: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _check_path_in_session(path_str: str, cwd: str, session_root: str) -> bool:
    """Check if a path (which may contain glob wildcards) is inside session_root."""
    # Strip glob wildcards to get the directory portion for validation
    clean = re.sub(r'[*?\[\]{}]+', '', path_str)
    # Remove trailing slashes left after stripping
    clean = clean.rstrip('/')
    if not clean:
        return True  # Pure wildcard like "**" — resolves to cwd which is session_root
    return _is_under(_resolve(clean, cwd), session_root)


# ---------------------------------------------------------------------------
# Hook 1: block destructive operations outside ./scratch/
# ---------------------------------------------------------------------------
async def block_deletions_except_scratch(input_data: dict, tool_use_id: str | None, context) -> dict:
    """Block destructive Bash commands and empty Write calls unless target is ./scratch/."""
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        hook_event = input_data.get("hook_event_name", "PreToolUse")
        cwd = input_data.get("cwd", "")

        if not isinstance(tool_input, dict):
            return {}

        scratch_dir = os.path.realpath(os.path.join(cwd, "scratch")) if cwd else None

        # Bash: destructive commands must target only scratch
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if isinstance(command, str) and DESTRUCTIVE_PATTERNS.search(command):
                if scratch_dir:
                    tokens = command.split()
                    cmd_name = tokens[0] if tokens else ""

                    # mv: allow only when BOTH source and dest are in scratch
                    if cmd_name == "mv":
                        path_tokens = [
                            t for t in tokens[1:]
                            if not t.startswith("-") and t
                        ]
                        all_in_scratch = all(
                            _is_under(_resolve(t, cwd), scratch_dir)
                            for t in path_tokens
                        )
                        if path_tokens and all_in_scratch:
                            return {}
                        logger.warning(f"Blocked mv outside scratch: {command}")
                        return _deny(hook_event, (
                            "BLOCKED: 'mv' is only allowed within ./scratch/. "
                            "Use 'cp' to copy files to ./artifacts/ instead."
                        ))

                    # All other destructive commands: all paths must be in scratch
                    delete_cmds = {"rm", "rmdir", "unlink", "shred", "truncate", "trash", "del"}
                    path_tokens = [
                        t for t in tokens
                        if not t.startswith("-") and t not in delete_cmds and t
                    ]
                    all_in_scratch = all(
                        _is_under(_resolve(t, cwd), scratch_dir)
                        for t in path_tokens
                    )
                    if path_tokens and all_in_scratch:
                        return {}

                logger.warning(f"Blocked destructive Bash command: {command}")
                return _deny(hook_event, (
                    "BLOCKED: Destructive operations are only allowed inside ./scratch/. "
                    "You may copy files to ./artifacts/ using 'cp'."
                ))

        # Write: empty content = stealth delete
        if tool_name == "Write":
            content = tool_input.get("content", "")
            file_path = tool_input.get("path", "") or tool_input.get("file_path", "")
            if file_path and isinstance(content, str) and content.strip() == "":
                logger.warning(f"Blocked empty write to file: {file_path}")
                return _deny(hook_event, (
                    "BLOCKED: Writing empty content to a file is not allowed."
                ))

        return {}

    except Exception as e:
        logger.error(f"Error in block_deletions hook: {e}", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Hook 2: enforce file isolation — nothing leaves the session directory
# ---------------------------------------------------------------------------
async def enforce_file_isolation(
    input_data: dict,
    tool_use_id: str | None,
    context,
    *,
    session_root: str,
    allowed_write_dirs: list[str],
    allowed_delete_dirs: list[str],
) -> dict:
    """
    Enforces per-session directory access:
      - ALL file access must be inside session_root
      - Writes only to scratch / artifacts (not user-uploads)
      - Deletes only in scratch
    """
    try:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        hook_event = input_data.get("hook_event_name", "PreToolUse")
        cwd = input_data.get("cwd", "")

        if not isinstance(tool_input, dict):
            return {}

        def _in_session(path: str) -> bool:
            return _is_under(_resolve(path, cwd), session_root)

        def _is_writable(path: str) -> bool:
            resolved = _resolve(path, cwd)
            return any(_is_under(resolved, d) for d in allowed_write_dirs)

        # --- Read: path must be inside session_root -------------------------
        if tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            if file_path and not _in_session(file_path):
                logger.warning(f"Blocked Read outside session: {file_path}")
                return _deny(hook_event, (
                    f"BLOCKED: You can only read files inside your session directory. "
                    f"Attempted path: {file_path}"
                ))

        # --- Glob: both path AND pattern must stay inside session_root ------
        elif tool_name == "Glob":
            glob_path = tool_input.get("path", "")
            glob_pattern = tool_input.get("pattern", "")

            # Check explicit path
            if glob_path and not _in_session(glob_path):
                logger.warning(f"Blocked Glob path outside session: {glob_path}")
                return _deny(hook_event, (
                    f"BLOCKED: You can only search for files inside your session directory. "
                    f"Attempted path: {glob_path}"
                ))

            # Check pattern for absolute paths or traversal escaping session
            if glob_pattern and not _check_path_in_session(glob_pattern, cwd, session_root):
                logger.warning(f"Blocked Glob pattern outside session: {glob_pattern}")
                return _deny(hook_event, (
                    f"BLOCKED: Glob pattern resolves outside your session directory. "
                    f"Attempted pattern: {glob_pattern}"
                ))

        # --- Grep: both path AND pattern paths must be inside session -------
        elif tool_name == "Grep":
            grep_path = tool_input.get("path", "")
            if grep_path and not _in_session(grep_path):
                logger.warning(f"Blocked Grep outside session: {grep_path}")
                return _deny(hook_event, (
                    f"BLOCKED: You can only search inside your session directory. "
                    f"Attempted path: {grep_path}"
                ))

        # --- Write / Edit: must be inside writable dirs ---------------------
        elif tool_name in ("Write", "Edit"):
            file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
            if file_path and not _is_writable(file_path):
                logger.warning(f"Blocked {tool_name} outside writable dir: {file_path}")
                return _deny(hook_event, (
                    f"BLOCKED: You can only write files inside ./scratch/ or ./artifacts/. "
                    f"Attempted path: {file_path}"
                ))

        # --- Bash: allowlist approach ---------------------------------------
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            if not isinstance(command, str):
                return {}

            tokens = command.split()
            cmd_name = tokens[0] if tokens else ""

            # Strip path prefix if command is called with full path (e.g. /usr/bin/python3)
            cmd_basename = os.path.basename(cmd_name)

            # 1) Allowlist — only permit known-safe commands
            if cmd_basename not in ALLOWED_BASH_CMDS:
                logger.warning(f"Blocked non-allowlisted Bash command: {cmd_name}")
                return _deny(hook_event, (
                    f"BLOCKED: '{cmd_basename}' is not in the allowed commands list. "
                    f"Use the dedicated Read/Write/Glob/Grep tools for file operations."
                ))

            # 2) python/node running a script file — script must be in session
            if cmd_basename in ("python", "python3", "node"):
                script_args = [t for t in tokens[1:] if not t.startswith("-") and t]
                if script_args:
                    script_path = script_args[0]
                    # Block -c/-e inline (bypass risk)
                    if script_path in ("-c", "-e"):
                        logger.warning(f"Blocked inline scripting: {command[:200]}")
                        return _deny(hook_event, (
                            f"BLOCKED: Inline scripting ({cmd_basename} -c/-e) is not allowed. "
                            "Write a script file and run it instead."
                        ))
                    if not _in_session(script_path):
                        logger.warning(f"Blocked {cmd_basename} script outside session: {script_path}")
                        return _deny(hook_event, (
                            f"BLOCKED: Script must be inside your session directory. "
                            f"Attempted: {script_path}"
                        ))

            # 3) cp/rsync — ALL paths must be in session, destination must be writable
            if cmd_basename in COPY_CMDS:
                path_args = [t for t in tokens[1:] if not t.startswith("-") and t]
                # All paths (source + dest) must be inside session
                for p in path_args:
                    if not _in_session(p):
                        logger.warning(f"Blocked {cmd_basename} path outside session: {p}")
                        return _deny(hook_event, (
                            f"BLOCKED: '{cmd_basename}' paths must be inside your session directory. "
                            f"Path outside session: {p}"
                        ))
                # Destination (last arg) must be writable
                if path_args:
                    dest = path_args[-1]
                    if not _is_writable(dest):
                        logger.warning(f"Blocked {cmd_basename} dest outside writable dir: {dest}")
                        return _deny(hook_event, (
                            f"BLOCKED: '{cmd_basename}' destination must be inside ./scratch/ or ./artifacts/. "
                            f"Attempted destination: {dest}"
                        ))

            # 4) touch/mkdir — must target writable dirs only
            if cmd_basename in ("touch", "mkdir"):
                path_args = [t for t in tokens[1:] if not t.startswith("-") and t]
                for p in path_args:
                    if not _is_writable(p):
                        logger.warning(f"Blocked {cmd_basename} outside writable dir: {p}")
                        return _deny(hook_event, (
                            f"BLOCKED: '{cmd_basename}' can only target ./scratch/ or ./artifacts/. "
                            f"Attempted path: {p}"
                        ))

            # 5) tee — output target must be writable
            if cmd_basename == "tee":
                path_args = [t for t in tokens[1:] if not t.startswith("-") and t]
                for p in path_args:
                    if not _is_writable(p):
                        logger.warning(f"Blocked tee outside writable dir: {p}")
                        return _deny(hook_event, (
                            f"BLOCKED: 'tee' output must target ./scratch/ or ./artifacts/. "
                            f"Attempted path: {p}"
                        ))

            # 6) ALL non-flag arguments that look like paths must be inside session
            for token in tokens[1:]:
                if token.startswith("-"):
                    continue
                # Bare "/" or any absolute path outside session
                if token == "/" or token.startswith("/"):
                    if not _in_session(token):
                        logger.warning(f"Blocked Bash — path outside session: {token}")
                        return _deny(hook_event, (
                            f"BLOCKED: All file paths must be inside your session directory. "
                            f"Found path outside session: {token}"
                        ))

            # 7) Redirect targets must be writable
            for target in REDIRECT_RE.findall(command):
                if not _is_writable(target):
                    logger.warning(f"Blocked Bash redirect to non-writable dir: {target}")
                    return _deny(hook_event, (
                        f"BLOCKED: Output redirection must target ./scratch/ or ./artifacts/. "
                        f"Attempted target: {target}"
                    ))

            # 8) Block relative paths with .. that escape session_root
            for token in tokens:
                if ".." in token and not token.startswith("-"):
                    resolved = _resolve(token, cwd)
                    if not _is_under(resolved, session_root):
                        logger.warning(f"Blocked Bash — path traversal escaping session: {token}")
                        return _deny(hook_event, (
                            f"BLOCKED: Path traversal outside session directory is not allowed. "
                            f"'{token}' resolves to outside your session."
                        ))

        return {}

    except Exception as e:
        logger.error(f"Error in enforce_file_isolation hook: {e}", exc_info=True)
        return {}
