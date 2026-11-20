# Edit evidence and integration map

This is a real source tree, not four text fields. The server integration report MUST map
native modules to the editable paths: prompt, planner/control flow, writer, memory graph,
retrieval, context handling, tool wrappers and skills. Preserve H0 behavior first.

Before editing, read the current code and actual traces. Explain a reusable mechanism,
when it activates, which successful behavior must be preserved, and why an instruction-only
change is or is not sufficient. Keep tags consistent with actual executable differences.

Historical replay is a causal ordered sequence, not an independent test set. Both current
and candidate versions start from the same historical memory checkpoint, receive each
historical label only after that replayed prediction, and may update memory between replayed
questions. The current live state is migrated separately before candidate promotion.
