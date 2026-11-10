# Proposed amendment — awaiting explicit user decision

This proposal has not been implemented or executed. The original R50 producer and configuration remain frozen.

The actual held case is `chexbench_openi_0078`, ordinal 317. MAIRA completed one 300-token generation (48.27794743003324 seconds), reached the existing limit without EOS, and left an unmatched `<obj>`. The original parser raised `AssertionError`; the existing guard correctly recorded a failed tool outcome. This is an observed model-output/parser failure, not a zero-generation loader fault.

Proposed continuation policy, only if explicitly approved:

- Keep this failed generation, its output, parser exception, physical cost/time and all original exit1 records unchanged. Never regenerate this failed selection or repair/truncate/close its output.
- Deliver an explicit **failed tool observation** to the main agent, stating that the call ended without usable grounding. Never label the tool or its generation policy healthy or successful.
- Apply this failure-delivery rule uniformly to the held case and all remaining questions in all three cohorts. Preserve the EOS policy, token limit, model parameters and ordinary stopping rules.
- Record the new execution code and the amendment boundary. Do not rewrite the 316 completed predictions. Resume only after checking saved-request text semantics and unknown-send protections.
- Treat the resulting experiment as amended R50. Disclose the different failure-handling policy and its time/order confound; include all sources and failures in the final complete-results review and publication.

Without explicit approval, retain the stopped incomplete run under its original frozen protocol. No new tool generation, queue launch, scoring or publication-ready marker is authorized by this proposal.
