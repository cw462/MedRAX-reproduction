# Restricted single-tool Agent smoke

`single_tool_agent_smoke.py` runs the upstream MedRAX `Agent` with the original `MEDICAL_ASSISTANT` system prompt, `ChatOpenAI`, `MemorySaver`, and only the official DenseNet classifier. It loads the Agent, utility parser and classifier by source file, avoiding `main.py` and `medrax.tools.__init__` imports of every model.

This is a functional smoke test. It is not the full tool set or a reproduction of paper metrics. The default is one question, with a hard maximum of three. It uses a new thread/checkpointer for each question and two graph phases in the same thread (multimodal reasoning, then the author's letter-only follow-up); the author notebook shares a thread across a case's questions. The user prompt preserves the author workflow in substance but does not reproduce its byte-for-byte formatting. Local images are encoded in data URLs and exposed as authorized local tool paths. All these differences must be reported.

Dependencies beyond the classifier environment are `langgraph`, `langchain-openai` and `python-dotenv`. Lock the actual installed versions and record the upstream source commit. Initialization may download weights before per-question invocation limits become active.

```sh
python experiments/single_tool_agent_smoke.py \
  --repo /path/to/MedRAX \
  --input /path/to/inference-only.jsonl \
  --images-root /path/to/images \
  --output /path/to/new-run \
  --model APPROVED_MODEL \
  --base-url https://APPROVED_PROVIDER/v1 \
  --device cuda:0 --max-cases 1 \
  --max-tool-calls 2 --max-model-calls 4 \
  --max-case-seconds 180 --request-timeout-seconds 60 \
  --max-output-tokens 512 --answer-mode two-stage \
  --require-tool-call
```

The API key is read from `OPENAI_API_KEY`, or one stdin line if `--api-key-stdin` is supplied. Never place a key in command-line arguments, project files or committed logs. Input must have exactly `question_id`, `question`, and `images`; reference answers and explanations are rejected. Every tool image must be one of the images provided for that question.

The model may legitimately choose not to call the tool. Such a run has `tool_execution_verified=false`; `--require-tool-call` returns nonzero if no valid classifier return was observed. The tool is not forcibly called to make a result look successful. A validated return means the call returned 18 finite model scores in range with the expected labels; it does not validate clinical correctness. Tool failures are recorded separately from invocation counts.

`trace.jsonl` records invocation counters, times, provider token counts when available, tool-call identifiers, image hashes and classifier scores. Raw model reasoning and reference labels are not saved; final output is parsed strictly as one choice letter. The result directory has a `.gitignore` excluding its contents. Treat predictions and tool outputs as research artifacts that may be sensitive; do not commit them automatically.

`summary.json` records source hashes, installed versions, limits and protocol differences. Token counts are provider-reported. `observed_usage_sum` retains unknown fields as null, and `usage_complete` is false unless every attempted model call reports all three token fields. Tool loops can cause each graph phase to make multiple model requests, subject to the common invocation limit. `actual_cost_usd` remains null: there is no monetary hard limit, and request limits cannot cancel an already running local tool. The script does not score answers, retry failed provider requests, or resume a partial run.

Offline guard tests use fabricated objects only:

```sh
python -m unittest discover -s experiments -p 'test_single_tool_agent_smoke.py' -v
```

The module has not itself been validated against a real server or API by its authoring agent; record the first real run separately.
