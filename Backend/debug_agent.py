"""
Quick debug script to test the new session flow end-to-end.

Usage:
    cd doc-agent
    WORKSPACE_DIR="./workspace" python debug_agent.py
"""

import asyncio
import json
import os
from pathlib import Path

# Fix nested session detection (when running inside Claude Code terminal)
if "CLAUDECODE" in os.environ:
    del os.environ["CLAUDECODE"]

# Must import after clearing CLAUDECODE
from app.agent import run_agent
from app.session_store import generate_session_id, get_session

WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "./workspace")).resolve()


async def main():
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"API key set: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
    print("=" * 60)

    # --- Turn 1: new session ------------------------------------------------
    session_id = generate_session_id()
    print(f"\n[Turn 1] Pre-generated session ID: {session_id}")
    print(f"[Turn 1] Session dir: {WORKSPACE_DIR / 'processed' / session_id}")

    try:
        result = await run_agent(
            instruction="Say hello and list the files in the uploads directory.",
            session_id=session_id,
        )
        print(f"[Turn 1] App session ID:  {result.session_id}")
        print(f"[Turn 1] SDK session ID:  {result.sdk_session_id}")
        print(f"[Turn 1] Result: {result.result[:200]}...")
        print(f"[Turn 1] Files modified: {result.files_modified}")
    except Exception as e:
        print(f"\n[Turn 1] ERROR: {type(e).__name__}: {e}")
        return

    # --- Show persisted session data ----------------------------------------
    print("\n" + "-" * 60)
    session_data = get_session(WORKSPACE_DIR, session_id)
    print(f"Persisted session:\n{json.dumps(session_data, indent=2)}")

    # --- Turn 2: resume same session ----------------------------------------
    print("\n" + "=" * 60)
    print(f"[Turn 2] Resuming session: {session_id}")

    try:
        result2 = await run_agent(
            instruction="What did we talk about before? Summarize our history.",
            session_id=session_id,
        )
        print(f"[Turn 2] Result: {result2.result[:200]}...")
        print(f"[Turn 2] History entries: {len(result2.history)}")
    except Exception as e:
        print(f"\n[Turn 2] ERROR: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Debug complete.")


asyncio.run(main())
