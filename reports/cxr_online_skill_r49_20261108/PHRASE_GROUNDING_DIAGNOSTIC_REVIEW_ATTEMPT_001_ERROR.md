# Reviewer request rejected before assessment

API Error: 402 Insufficient Balance (request_id: 95841385-f4dc-4307-b45c-a2d9279b58ea)

No score, verdict or scope-complete assessment was produced. Native exit1; CLI-reported usage/cost0 is not a provider invoice. No diagnostic invocation occurred.

```json
{
  "is_error": true,
  "duration_api_ms": 0,
  "num_turns": 1,
  "stop_reason": "stop_sequence",
  "session_id": "3a5c1476-d0b2-472e-970e-ba5aa16cbde4",
  "total_cost_usd": 0,
  "usage": {
    "input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 0,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 0,
      "ephemeral_5m_input_tokens": 0
    },
    "inference_geo": "",
    "iterations": [],
    "speed": "standard"
  },
  "modelUsage": {},
  "permission_denials": [],
  "terminal_reason": "api_error",
  "fast_mode_state": "off",
  "fast_mode_disabled_reason": "sdk_opt_in_required",
  "subtype": "success",
  "api_error_status": 402,
  "result": "API Error: 402 Insufficient Balance (request_id: 95841385-f4dc-4307-b45c-a2d9279b58ea)",
  "type": "result",
  "duration_ms": 6449,
  "uuid": "10ee9d7b-7069-4cee-8759-21777c9d5a2f"
}
```
