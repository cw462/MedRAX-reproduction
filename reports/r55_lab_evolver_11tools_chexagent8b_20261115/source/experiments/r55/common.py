"""Shared no-GT inference and deterministic answer-handling utilities."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open('r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError('not an object')
                yield obj
            except Exception as e:
                raise ValueError(f'{path}:{ln}: {e}') from e


def json_line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'


def atomic_json(path: Path, obj: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def compact_observations(observations: Any, max_items: int = 8, max_chars: int = 850) -> list[dict]:
    """Allowlist only saved tool *outputs*. Never relay a main-model transcript.

    R54 main_model_calls may contain released GT for EARLIER same-image questions.
    This function deliberately does not see that field.
    """
    if not isinstance(observations, list):
        return []
    safe = []
    for ob in observations[:max_items]:
        if not isinstance(ob, dict):
            continue
        content = ob.get('observation')
        if isinstance(content, str):
            excerpt = content
        elif content is None:
            excerpt = ''
        else:
            excerpt = json.dumps(content, ensure_ascii=False, default=str)
        safe.append({
            'tool': str(ob.get('tool') or ob.get('backend') or 'unknown')[:60],
            'status': str(ob.get('status') or 'unknown')[:40],
            'excerpt': excerpt[:max_chars],
        })
    return safe


def normalized_text(value: Any) -> str:
    text = str(value or '').strip().casefold()
    text = re.sub(r'^\s*(?:answer\s*:\s*)', '', text)
    text = re.sub(r'[\s\.,;:!?()\[\]{}"\'`]+', ' ', text).strip()
    return text


def canonical_yes_no(answer: Any) -> str | None:
    a = normalized_text(answer)
    if a in {'yes', 'y', 'true', 'present', 'positive', '有', '是'}:
        return 'yes'
    if a in {'no', 'n', 'false', 'absent', 'negative', '无', '否'}:
        return 'no'
    return None


def canonical_choice(answer: Any, options: dict | None) -> str | None:
    """Match letter or COMPLETE choice text; never match loose substrings."""
    if not isinstance(options, dict) or not options:
        return None
    opts = {str(k).upper(): normalized_text(v) for k, v in options.items()}
    text = str(answer or '').strip()
    if not text:
        return None
    m = re.fullmatch(r'\s*\(?([A-Z])\)?(?:[\.:\)]\s*)?', text, flags=re.I)
    if m and m.group(1).upper() in opts:
        return m.group(1).upper()
    text_norm = normalized_text(text)
    # R54 often emits 'B. complete original choice' instead of only 'B'.
    prefixed = re.match(r'^\s*([A-Z])[\.\):\-]\s+(.+)$', text, flags=re.I | re.S)
    if prefixed:
        candidate = prefixed.group(1).upper()
        if candidate in opts and normalized_text(prefixed.group(2)) == opts[candidate]:
            return candidate
    matches = [k for k, v in opts.items() if v == text_norm]
    return matches[0] if len(matches) == 1 else None


def answer_is_unchanged(new: Any, old: Any, options: dict | None) -> bool:
    a = canonical_choice(new, options)
    b = canonical_choice(old, options)
    if a is not None and b is not None:
        return a == b
    a_yn, b_yn = canonical_yes_no(new), canonical_yes_no(old)
    if a_yn and b_yn:
        return a_yn == b_yn
    return normalized_text(new) == normalized_text(old)


def valid_answer(answer: Any, options: dict | None) -> bool:
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 180:
        return False
    if isinstance(options, dict) and options:
        return canonical_choice(answer, options) is not None
    if '\n' in answer or '{' in answer or '}' in answer:
        return False
    return True


def parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I | re.S).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        pos = text.find('{')
        if pos < 0:
            raise ValueError('no JSON object in model output')
        obj, _ = dec.raw_decode(text[pos:])
    if not isinstance(obj, dict):
        raise ValueError('model output is not a JSON object')
    return obj


def resolve_images(row: dict, roots: dict[str, str], max_bytes: int = 12 * 1024 * 1024) -> tuple[list[Path], list[dict]]:
    """Resolve only inside user-provided dataset roots; fail closed on missing inputs."""
    dataset = row['dataset']
    if dataset not in roots:
        return [], [{'error': f'missing --{dataset}-root'}]
    base = Path(roots[dataset]).expanduser().resolve()
    found, evidence = [], []
    for image in row.get('images', []):
        rel = Path(str(image))
        if rel.is_absolute() or '..' in rel.parts:
            return [], [{'image': str(image), 'error': 'unsafe image path'}]
        candidates = [base / rel]
        if rel.parts and rel.parts[0] == 'images':
            candidates.append(base.joinpath(*rel.parts[1:]))
        match = None
        for candidate in candidates:
            c = candidate.resolve()
            if c.is_relative_to(base) and c.is_file():
                match = c
                break
        if match is None:
            evidence.append({'image': str(image), 'error': 'not found in dataset root'})
            continue
        size = match.stat().st_size
        if size == 0 or size > max_bytes:
            evidence.append({'image': str(image), 'error': f'invalid size {size}'})
            continue
        found.append(match)
        evidence.append({'image': str(image), 'sha256': sha256_file(match), 'bytes': size})
    if len(found) != len(row.get('images', [])) or not found:
        return [], evidence
    return found, evidence
