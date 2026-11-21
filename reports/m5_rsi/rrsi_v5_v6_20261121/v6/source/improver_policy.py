"""Versioned role instructions for MedRAX P search and R revision."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

from .io import ProtocolError, read_json


P_SEARCH_ROLES = ("analyst", "digester", "proposer", "critic")
ROLES = (*P_SEARCH_ROLES, "meta")


@dataclass(frozen=True)
class ImproverPolicy:
    version: str
    parent_version: str | None
    hypothesis: str
    roles: tuple[tuple[str, str], ...]
    source_path: Path | None = None

    @classmethod
    def load(cls, path):
        source = Path(path).resolve()
        data = read_json(source)
        if not isinstance(data, dict) or set(data) != {"version", "parent_version", "hypothesis", "roles"}:
            raise ProtocolError(f"invalid improver policy fields: {source}")
        roles = data["roles"]
        if not isinstance(roles, dict) or set(roles) != set(ROLES):
            raise ProtocolError(f"invalid improver role set: {source}")
        if any(not isinstance(value, str) for value in roles.values()):
            raise ProtocolError(f"improver instructions must be text: {source}")
        for name in ("version", "hypothesis"):
            if not isinstance(data[name], str) or not data[name].strip():
                raise ProtocolError(f"invalid improver {name}: {source}")
        parent = data["parent_version"]
        if parent is not None and (not isinstance(parent, str) or not parent.strip() or parent == data["version"]):
            raise ProtocolError(f"invalid improver parent version: {source}")
        return cls(data["version"], parent, data["hypothesis"], tuple((role, roles[role]) for role in ROLES), source)

    def to_dict(self):
        return {
            "version": self.version,
            "parent_version": self.parent_version,
            "hypothesis": self.hypothesis,
            "roles": dict(self.roles),
        }

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except FileExistsError:
            if read_json(path) != data:
                raise ProtocolError(f"improver policy already exists with different contents: {path}") from None
        return path

    def system_prompt(self, role, system=None):
        instruction = dict(self.roles)[role]
        if not instruction:
            return system
        return f"{system or ''}\n\nMedRAX {role} strategy ({self.version}):\n{instruction}"

    def propose_revision(self, client, development_search_history, trigger_evidence, *,
                         candidate_version="R1", model=None):
        """Ask the active R to revise one role using the configured search model."""
        if not isinstance(candidate_version, str) or not candidate_version.strip() or candidate_version == self.version:
            raise ProtocolError("candidate must have a distinct improver version")
        system = self.system_prompt("meta", (
            "You revise the MedRAX improvement policy R, which diagnoses trajectories and proposes changes to "
            "the answering program P. Propose one transferable revision to one P-search role: analyst, digester, "
            "proposer or critic. Supply a complete replacement for that role's supplemental instruction. Keep the "
            "other role strategies and the evaluator, data access, feedback timing, scoring and budget fixed. "
            "Use the diagnostic evidence to improve how R selects a P change, without embedding case IDs, "
            "question text or answers in R. Return exactly a JSON object with string fields role, instruction, "
            "and hypothesis. The hypothesis should name one mechanism and its intended effect."
        ))
        prompt = json.dumps({
            "mode": "improve_improver",
            "active_policy": self.to_dict(),
            "development_search_history": development_search_history,
            "trigger_evidence": trigger_evidence,
        }, ensure_ascii=False)
        raw = client.generate(prompt, system=system, json_only=True, model=model, max_tokens=2400)
        try:
            edit = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ProtocolError("improver revision did not return JSON") from exc
        if not isinstance(edit, dict) or set(edit) != {"role", "instruction", "hypothesis"}:
            raise ProtocolError("improver revision may only specify role, instruction and hypothesis")
        if any(not isinstance(value, str) or not value.strip() for value in edit.values()):
            raise ProtocolError("improver revision fields must be nonempty text")
        role = edit["role"].strip()
        roles = dict(self.roles)
        instruction = edit["instruction"].strip()
        if role not in P_SEARCH_ROLES or roles[role] == instruction:
            raise ProtocolError("improver revision must change one role exercised by the P search trials")
        roles[role] = instruction
        return replace(self, version=candidate_version, parent_version=self.version,
                       hypothesis=edit["hypothesis"].strip(), roles=tuple(roles.items()), source_path=None)
