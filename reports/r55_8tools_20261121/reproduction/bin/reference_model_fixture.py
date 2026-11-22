"""Deterministic, loopback-only chat responses for upstream integration tests."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread


MODEL_ID = "paper2agent-memory-fixture"
SUMMARY = "Step 0: Read the feather count.\nStep 1: Divide and round up.\nConclusion: The minimum count follows from the total usable feathers."
PLAN = "Calculate the total shuttlecock feathers from the per-item requirement. Divide by the usable feathers per goose and round up."
WORKFLOW = {
    "agent_planning": PLAN,
    "search_agent_planning": "Identify which measurements are provided before deciding whether evidence needs to be retrieved. Confirm the calculation against the stated constraint.",
    "agent_experience": "Use the whole-number ceiling when estimating minimum suppliers from a count and capacity. Keep the denominator in the same unit as the numerator.",
    "search_agent_experience": "For calculation tasks with all inputs already supplied, distinguish assumptions from observed values. Verify the result by multiplication before submitting it.",
}
SKILL = '''```python
def minimum_suppliers(total_units: int, capacity: int) -> int:
    """Compute the minimum suppliers for a total quantity and per-supplier capacity."""
    return (total_units + capacity - 1) // capacity
```'''


def completion_for(prompt):
    """Dispatch by recognizable upstream prompt sections."""
    if "Generate an ultra-concise summary of the agent's actions" in prompt:
        return "summary", SUMMARY
    if "extract simple, actionable insights" in prompt:
        if "following failed task execution" in prompt:
            return "expel_failure", "Avoid rounding the feather count down when computing minimum suppliers.\nCheck that the computed goose count covers all required shuttlecock feathers."
        return "expel_success", "Multiply the shuttlecock count by the required feathers per shuttlecock.\nRound the number of geese up to the next whole supplier."
    if "create a structured step-by-step summary" in prompt:
        return "expel_trajectory", "1. Determine total shuttlecock feathers.\n2. Divide by usable feathers per goose.\n3. Round up.\n4. Check coverage."
    if "distilling abstract procedural knowledge" in prompt:
        return "memp_script", "<script>Calculate the aggregate demand, divide by unit capacity, and round up.</script>"
    if "[New Failed Trace]" in prompt:
        return "memp_adjustment", json.dumps({
            "procedural_script": "Calculate aggregate demand and round up the quotient. Verify capacity covers demand before returning the minimum.",
            "concrete_steps_summary": "The prior result rounded down. Check that the candidate count covers every required feather.",
        })
    if "extract high-quality memory patterns" in prompt:
        return "agent_kb_store", json.dumps(WORKFLOW)
    if "Here is the user query:" in prompt:
        return "agent_kb_focus", prompt.rsplit("Here is the user query:", 1)[1].strip()
    if "multiple experience entries" in prompt or "Analyze similar tasks and past experiences" in prompt:
        return "agent_kb_guidance", "1. Compute total feather demand.\n2. Divide by usable feathers per supplier and round up."
    if "Extract ABSTRACT, GENERALIZABLE patterns" in prompt:
        return "cerebra_graph", json.dumps({
            "highlights": PLAN,
            "patterns": ["Calculate total shuttlecock feathers and use the ceiling of the supply ratio."],
            "playbooks": {"feather quantity planning": "Compute usable feather supply before dividing total feather demand."},
            "checklists": ["Verify that the selected goose count meets the total feather requirement."],
        })
    if "Generate a retrieval focus for semantic search" in prompt:
        focus = next(line[6:] for line in prompt.splitlines() if line.startswith("Task: "))
        return "cerebra_focus", json.dumps({"retrieval_focus": focus})
    if "Provide OPTIONAL REFERENCE" in prompt:
        return "cerebra_guidance", "Similar tasks have computed total feather demand first. A capacity check confirmed the rounded-up count."
    if "Create a REUSABLE, GENERIC tool function" in prompt:
        return "cerebra_tool", SKILL
    if "You are a tool selection agent" in prompt:
        return "cerebra_route", '["minimum_suppliers"]'
    if "extract actionable tips for future similar tasks" in prompt:
        return "mobilee_tips", "Calculate the total feather demand before dividing by supplier capacity.\nRound up before checking that supply covers demand."
    if "create a reusable action sequence (shortcut)" in prompt:
        return "mobilee_shortcut", json.dumps({
            "name": "capacity_count", "description": "Calculate minimum suppliers for aggregate feather demand.",
            "precondition": "Demand and capacity are known.",
            "atomic_action_sequence": [{"name": "calculate", "arguments_map": {"task": PLAN}}],
        })
    if "extract a GENERAL, PARAMETERIZED skill" in prompt:
        return "skillweaver", SKILL
    if "extract a generic, reusable workflow" in prompt:
        return "workflow", json.dumps({"workflow": PLAN})
    if "on a scale of 1-10" in prompt and "Success Case:" in prompt:
        return "generative_rank", "Score: 8"
    if "The trajectory is about finding an egg" in prompt:
        return "voyager_trajectory", PLAN
    if "Summarize this agent task execution trajectory" in prompt:
        return "cheatsheet_summary", SUMMARY
    if '"dynamic cheatsheet" curator' in prompt:
        return "cheatsheet_curate", "<cheatsheet>Convert inputs to a common unit. Use a ceiling for minimum counts. Verify capacity after rounding.</cheatsheet>"
    if "**Extract TWO types" in prompt:
        return "lightweight_extract", json.dumps({
            "strategic": [{"content": PLAN, "applies_when": "Capacity and demand are known.",
                           "do_not_apply_when": "Supplier capacities differ.", "provenance": {
                               "source_type": "trajectory", "source_url": None,
                               "evidence_span": "Compute the minimum supplier count.",
                               "confidence": 0.9, "expires_at": None,
                           }}],
            "operational": [],
        })
    if "judging whether stored memories apply" in prompt:
        return "lightweight_rerank", '{"judgments":[{"index":1,"similarity":0.9,"applies":true,"risk":"low","reason":"Shared capacity calculation"}]}'
    if '"selected_indices"' in prompt and '"guidance"' in prompt:
        return "lightweight_guidance", json.dumps({"selected_indices": [1], "guidance": PLAN})
    if '"key_extracts"' in prompt:
        return "lightweight_extract_short", '{"key_extracts":[]}'
    if "Single Pure-Text Narrative" in prompt:
        return "evolver_narrative", PLAN
    if 'extract a "Guiding Principle"' in prompt or 'extract a "Cautionary Principle"' in prompt:
        return "evolver_principle", '[DESCRIPTION]:\nUse a whole-number ceiling for capacity planning.\n[STRUCTURE]:\n[["demand", "divided_by", "capacity"]]'
    if "Please answer with only" in prompt and "Principle A:" in prompt:
        return "evolver_dedup", "Yes"
    return "unmapped", "UNMAPPED FIXTURE PROMPT"


def message_text(messages):
    texts = []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        else:
            texts.extend(part["text"] for part in content if part.get("type") == "text")
    return "\n".join(texts)


@contextmanager
def reference_model_server():
    """Yield a local OpenAI-compatible endpoint and a trace of matched routes."""
    calls = []

    class FixtureHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = message_text(request["messages"])
            route, content = completion_for(prompt)
            record = {"route": route}
            if route == "unmapped":
                record["prompt_prefix"] = prompt.strip()[:200]
            calls.append(record)
            payload = json.dumps({
                "id": "chatcmpl-paper2agent-fixture", "object": "chat.completion", "created": 1,
                "model": request.get("model", MODEL_ID),
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1", calls
        finally:
            server.shutdown()
            thread.join()
