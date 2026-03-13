"""
Manual MLflow tracing for the Claude Agent SDK.

Why manual?
-----------
The SDK's query() spawns a Node.js subprocess (Claude Code CLI) that makes
the actual LLM API calls. MLflow auto-tracing monkey-patches Python SDK
clients (like openai.OpenAI()), but there's nothing to intercept on the
Python side — it just reads/writes JSON over stdin/stdout to the subprocess.

Instead, we build trace trees from the streaming events we DO receive:

    Root span: agent_run
      ├── tool:Read       (child span per tool call)
      ├── tool:Write
      ├── tool:Bash
      └── ...

All tracer methods are no-op safe: if tracing init fails, the agent keeps
running normally. Tracing errors never propagate to the caller.
"""

import json
import logging
from typing import Any

import mlflow
from mlflow.entities import SpanStatusCode

logger = logging.getLogger(__name__)


class AgentTracer:
    """Manages a single MLflow trace for one agent execution.

    Usage::

        tracer = AgentTracer()
        tracer.start(session_id="abc", instruction="Summarize the doc")

        tracer.start_tool("Read")
        tracer.end_tool("Read", summary="/uploads/report.docx")

        tracer.start_tool("Write")
        tracer.end_tool("Write", summary="writing /processed/summary.txt")

        tracer.end(result="Done.", turns=5, cost_usd=0.03)
    """

    def __init__(self) -> None:
        self._client = mlflow.MlflowClient()
        self._trace_id: str | None = None
        self._root_span_id: str | None = None
        self._active_span: Any = None       # current tool Span object
        self._active_tool: str | None = None
        self._turn_count: int = 0
        self._ok: bool = False              # True once root trace is open

    # ------------------------------------------------------------------
    # Root trace lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        *,
        session_id: str,
        instruction: str,
        is_resume: bool = False,
        uploaded_files: list[str] | None = None,
    ) -> None:
        """Open the root trace span."""
        try:
            inputs: dict[str, Any] = {
                "instruction": instruction,
                "session_id": session_id,
            }
            if uploaded_files:
                inputs["uploaded_files"] = uploaded_files

            root = self._client.start_trace(
                name="agent_run",
                inputs=inputs,
                tags={
                    "session_id": session_id,
                    "is_resume": str(is_resume),
                },
            )
            self._trace_id = root.trace_id
            self._root_span_id = root.span_id
            self._ok = True
            logger.debug(f"Trace started: trace_id={self._trace_id}")
        except Exception as e:
            logger.warning(f"Tracing: start failed: {e}")

    def end(
        self,
        *,
        result: str = "",
        turns: int = 0,
        cost_usd: float | None = None,
        error: str | None = None,
    ) -> None:
        """Close the root trace span. Safe to call multiple times (second call is a no-op)."""
        if not self._ok:
            return
        try:
            # Close orphan tool span if the stream was interrupted mid-tool
            if self._active_span:
                self._end_active_tool("(interrupted)")

            outputs: dict[str, Any] = {}
            if result:
                outputs["result"] = result[:2000]
            if turns:
                outputs["turns_used"] = turns
            if cost_usd is not None:
                outputs["cost_usd"] = cost_usd
            if error:
                outputs["error"] = error

            self._client.end_trace(
                trace_id=self._trace_id,
                outputs=outputs,
                status=SpanStatusCode.ERROR if error else SpanStatusCode.OK,
            )
            logger.debug(f"Trace ended: trace_id={self._trace_id}")
        except Exception as e:
            logger.warning(f"Tracing: end failed: {e}")
        finally:
            self._ok = False

    # ------------------------------------------------------------------
    # Tool span lifecycle
    # ------------------------------------------------------------------

    def start_tool(self, tool_name: str) -> None:
        """Open a child span for a tool call."""
        if not self._ok:
            return
        try:
            # Safety: close previous tool span if still open (shouldn't happen
            # with sequential content blocks, but guard against it)
            if self._active_span:
                self._end_active_tool("(superseded)")

            self._active_span = self._client.start_span(
                name=f"tool:{tool_name}",
                trace_id=self._trace_id,
                parent_id=self._root_span_id,
                span_type="TOOL",
                inputs={"tool_name": tool_name},
            )
            self._active_tool = tool_name
        except Exception as e:
            logger.warning(f"Tracing: start_tool({tool_name}) failed: {e}")

    def end_tool(
        self,
        tool_name: str,
        summary: str = "",
        tool_input: str = "",
    ) -> None:
        """Close the active tool span with its summary and raw input."""
        if not self._ok or not self._active_span:
            return

        outputs: dict[str, Any] = {"summary": summary}

        # Try to parse the accumulated tool input JSON for structured output
        if tool_input:
            try:
                outputs["input"] = json.loads(tool_input)
            except (json.JSONDecodeError, TypeError):
                outputs["input_raw"] = tool_input[:500]

        self._end_active_tool(summary, outputs=outputs)

    def record_turn(self, turn: int) -> None:
        """Track the turn counter (stored on the root trace at end)."""
        self._turn_count = turn

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _end_active_tool(
        self, summary: str, outputs: dict[str, Any] | None = None
    ) -> None:
        """Close whatever tool span is currently open."""
        try:
            final_outputs = outputs or {"summary": summary}
            if "tool_name" not in final_outputs:
                final_outputs["tool_name"] = self._active_tool or ""

            self._client.end_span(
                trace_id=self._trace_id,
                span_id=self._active_span.span_id,
                outputs=final_outputs,
                status=SpanStatusCode.OK,
            )
        except Exception as e:
            logger.warning(f"Tracing: end span for {self._active_tool} failed: {e}")
        finally:
            self._active_span = None
            self._active_tool = None
