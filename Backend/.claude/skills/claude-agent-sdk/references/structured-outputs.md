# Structured Outputs

Return validated, typed JSON from agent workflows.

## Table of Contents
- [Overview](#overview)
- [Quick start](#quick-start)
- [Type-safe with Zod (TypeScript)](#type-safe-with-zod-typescript)
- [Type-safe with Pydantic (Python)](#type-safe-with-pydantic-python)
- [Error handling](#error-handling)
- [Tips](#tips)

---

## Overview

Pass a JSON Schema to `output_format` / `outputFormat`. The agent can use tools freely, then returns validated JSON in `ResultMessage.structured_output` at the end.

Supported JSON Schema features: objects, arrays, strings, numbers, booleans, null, `enum`, `const`, `required`, nested objects, `$ref` definitions.

---

## Quick start

```python
# Python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

schema = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "founded_year": {"type": "number"},
        "headquarters": {"type": "string"},
    },
    "required": ["company_name"],
}

async def main():
    async for message in query(
        prompt="Research Anthropic and provide key company information",
        options=ClaudeAgentOptions(
            output_format={"type": "json_schema", "schema": schema}
        ),
    ):
        if isinstance(message, ResultMessage) and message.structured_output:
            print(message.structured_output)
            # {'company_name': 'Anthropic', 'founded_year': 2021, 'headquarters': 'San Francisco, CA'}

asyncio.run(main())
```

```typescript
// TypeScript
import { query } from "@anthropic-ai/claude-agent-sdk";

const schema = {
  type: "object",
  properties: {
    company_name: { type: "string" },
    founded_year: { type: "number" },
    headquarters: { type: "string" },
  },
  required: ["company_name"],
};

for await (const message of query({
  prompt: "Research Anthropic and provide key company information",
  options: { outputFormat: { type: "json_schema", schema } }
})) {
  if (message.type === "result" && message.structured_output) {
    console.log(message.structured_output);
  }
}
```

---

## Type-safe with Zod (TypeScript)

```typescript
import { z } from "zod";
import { query } from "@anthropic-ai/claude-agent-sdk";

const FeaturePlan = z.object({
  feature_name: z.string(),
  summary: z.string(),
  steps: z.array(z.object({
    step_number: z.number(),
    description: z.string(),
    estimated_complexity: z.enum(["low", "medium", "high"]),
  })),
  risks: z.array(z.string()),
});

type FeaturePlan = z.infer<typeof FeaturePlan>;

for await (const message of query({
  prompt: "Plan how to add dark mode to a React app",
  options: { outputFormat: { type: "json_schema", schema: z.toJSONSchema(FeaturePlan) } }
})) {
  if (message.type === "result" && message.structured_output) {
    const parsed = FeaturePlan.safeParse(message.structured_output);
    if (parsed.success) {
      const plan: FeaturePlan = parsed.data;
      console.log(`Feature: ${plan.feature_name}`);
      plan.steps.forEach(s => console.log(`${s.step_number}. [${s.estimated_complexity}] ${s.description}`));
    }
  }
}
```

---

## Type-safe with Pydantic (Python)

```python
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

class Step(BaseModel):
    step_number: int
    description: str
    estimated_complexity: str  # 'low', 'medium', 'high'

class FeaturePlan(BaseModel):
    feature_name: str
    summary: str
    steps: list[Step]
    risks: list[str]

async def main():
    async for message in query(
        prompt="Plan how to add dark mode to a React app",
        options=ClaudeAgentOptions(
            output_format={"type": "json_schema", "schema": FeaturePlan.model_json_schema()}
        ),
    ):
        if isinstance(message, ResultMessage) and message.structured_output:
            plan = FeaturePlan.model_validate(message.structured_output)
            print(f"Feature: {plan.feature_name}")
            for step in plan.steps:
                print(f"{step.step_number}. [{step.estimated_complexity}] {step.description}")
```

---

## Error handling

Check `message.subtype` to distinguish success from failure:

```python
# Python
async for message in query(prompt=..., options=...):
    if isinstance(message, ResultMessage):
        if message.subtype == "success" and message.structured_output:
            print(message.structured_output)
        elif message.subtype == "error_max_structured_output_retries":
            print("Could not produce valid structured output — simplify schema or prompt")
```

```typescript
// TypeScript
for await (const msg of query({ prompt: ..., options: ... })) {
  if (msg.type === "result") {
    if (msg.subtype === "success" && msg.structured_output) {
      console.log(msg.structured_output);
    } else if (msg.subtype === "error_max_structured_output_retries") {
      console.error("Could not produce valid output");
    }
  }
}
```

---

## Tips

- Keep schemas focused — deeply nested required fields are harder to satisfy
- Make optional what might not always be available (`"required"` only for fields always present)
- Use clear prompts — ambiguity makes it hard for the agent to know what to output
- Structured output appears in final `ResultMessage.structured_output` only, not as streaming tokens
