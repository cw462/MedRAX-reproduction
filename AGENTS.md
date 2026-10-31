# MedRAX experiment workflow

## Persistent user preference (2026-10-31)

After each experiment finishes, proactively publish its detailed results and interpretation to this repository's GitHub remote. Do not wait for the user to ask again. Publication is part of completing an experiment, not a new paid experiment.

Include the actual protocol/configuration, code, complete-denominator scores, per-question predictions and changes, corrections/harms/net gain, decision and tool observations, failure/recovery records, costs, timing and reproduction links. Explain what the evidence proves and what remains a hypothesis. Score only after generation completes; keep technical-failure recovery distinct from correction of a legal wrong answer.

The user explicitly wants benchmark question/case text, complete options, relevant original images and local/tool-derived images published so GPT can inspect concrete errors. This supersedes earlier instructions to keep all cases/images local. Preserve source attribution and applicable terms; remove identifying private patient information if encountered. Do not publish credentials, API/private keys, model weights or unrelated local files. Stage an explicit publication allowlist rather than whole private runs/data directories.

Keep monitoring lightweight. Do not rerun predictions or add repeated tests, audits, hashes or ledger scans just to publish a completed experiment. Perform only the content checks necessary for the outgoing publication. Never modify completed prediction records.

Report publication as complete only after the push succeeds and the remote commit is confirmed. Provide the report URL and commit ID; describe any actual publication blocker accurately.
