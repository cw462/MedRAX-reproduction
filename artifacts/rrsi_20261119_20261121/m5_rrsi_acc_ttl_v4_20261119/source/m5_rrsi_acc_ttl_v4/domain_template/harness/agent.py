"""Editable M5 entrypoint: SERVER CODEX must transplant the real initial M5 here.
All planning, prompts, retrieval, writing, graph maintenance and helper modules
that should evolve must be local imports in this tree, not a global old M5 install.
Do NOT replace the baseline with newly invented reasoning code.
"""

def initialize(state_dir, services):
    raise RuntimeError("Transplant the real M5 empty-memory initialization")

def predict(case, state_dir, services):
    """No feedback argument. Return {answer: str, trace: real action/tool records}."""
    raise RuntimeError("Transplant the real M5 inference and tool pipeline")

def observe(case, prediction, feedback, state_dir, services):
    """Called once after answer lock; feedback includes released reference in full_label mode."""
    raise RuntimeError("Transplant the real M5 memory writer")

def migrate(state_dir, services):
    """Must accept the previous version's committed memory state; no-op if schema unchanged.
    If candidate edits schema, include a deterministic migration. Never delete all memory
    merely to make an incompatible schema appear to work.
    """
    return {}
