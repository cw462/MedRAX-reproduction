# Validation30 protocol preparation — no real execution

`validation_protocol.py` currently implements **offline plan generation and a strict stage-budget adapter only**. It has no model-execution or resume CLI. No validation results are claimed. The prior first-ten classifier-only repeated design was never executed and is superseded by V3.

The user subsequently required all intended tools to pass real execution checks before a formal comparison is frozen. The two/three-tool, five-case runs are functional checks only and must not be entered as the formal baseline. This preparatory module's current registry validator supports two/three original tools; it therefore also needs an explicit reviewed extension and new frozen plan after full-tool readiness. Paid validation experiments are not authorized by this file.

The new plan consumes the independently frozen validation30 directory, its original split manifest/index, a prior real tool-registry manifest, and an existing shared-ledger snapshot. It does not inherit the old fifty-question inference manifest or read results, labels or explanations. It verifies question/case membership, all original image bytes and ordering, and the selection/audit hash chain.

The fixed schedule is 30 cases × two caps (512/1024) × three repeats × direct/Agent = 360 planned arm outcomes. Seed `20261027` shuffles the four cap/arm combinations within each replicate/question block; it does not seed provider sampling. Six slice plans each retain 30 questions and 60 arm outcomes. No started/terminal records or finalization marker are fabricated by the planner: every outcome is pending.

The available original classifier/report registry, optionally segmentation, is frozen from prior real provenance. Planning checks official source versions but does not reload weights or prove current GPU readiness. The future execution entry must revalidate the complete tool assets/environment under the frozen plan, reuse the unchanged `multi_tool_eval.run_arm`, and explicitly configure model output caps. Cap 512 uses the original `MoneyGuard`; cap 1024 uses `ChunkedBudgetGuard(1024)` around that same locked ledger. The chunk adapter does not support a 512 effective cap.

The planner checks the ledger schema, checksum, identity, policy and reconciled charges without constructing `MoneyGuard`, recovering pending requests or writing the ledger. A pending/live request or changing snapshot prevents planning. This is a read-only snapshot, not an execution lock. Future execution must acquire the original ledger lock and revalidate identity/state before every call path.

`--stage-state` is a private persistent origin file. Its first creation records the same ledger's current cumulative occupied amount; later plans reuse that origin and cannot change its ledger ID or stage limit. Other charges on the same ledger after that origin are conservatively included. The original ¥100 hard ceiling remains unchanged. The CLI retains the name `--stage-soft-limit-cny`, but the implemented request rule is strict: **cumulative stage occupancy plus the entire next-request worst-case reservation must fit**. The required reservation is ¥2.60096 at 512 or ¥5.20192 at 1024. Insufficient stage or hard balance blocks before even the first underlying block is reserved. Never create a new stage-state merely to reset allowance for more experiments.

Inspect the supported interface:

```bash
python experiments/validation_protocol.py --help
python -m unittest discover -s experiments -p 'test_validation_protocol.py' -v
```

Plan-only invocation, with private paths and a previously agreed stage limit:

```bash
python experiments/validation_protocol.py \
  --validation-dir /private/validation30_v3 \
  --split-directory /private/prepared_v2 \
  --repo /private/official-MedRAX \
  --ledger /private/original-shared-ledger.json \
  --expected-ledger-id "$ORIGINAL_LEDGER_ID" \
  --tool-manifest /private/real-tool-run/manifest.json \
  --stage-state /private/validation-stage-origin.json \
  --stage-soft-limit-cny "$AGREED_STAGE_LIMIT_CNY" \
  --output /private/new-validation-plan
```

The output is a root manifest, all-pending summary and six slice plans. It is **not runnable evidence** and must not be fed to a scorer as completed results. A later execution implementation needs durable root/slice journals, interrupted-start no-retry recovery, global API failure stops, unchanged stage origin, per-call stage guard, full unrun denominators and finalized hash markers. Independent scoring then reports each cap/repeat's paired outcomes; repeat-averaged cap differences must average within case before case-cluster bootstrap. Repeated requests are not independent cases.

The synthetic tests exercise the strict request boundary, both accounting adapters, ledger identity, no mutation during snapshot reads, forbidden label reads, stage reuse, complete image checks, schedule balance and all-pending outputs. A separate read-only check loaded the real 30-case/51-image input and produced the 360-item schedule in memory without opening a ledger or calling a model.
