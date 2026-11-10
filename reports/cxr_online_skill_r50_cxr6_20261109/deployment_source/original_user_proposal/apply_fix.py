"""Apply the one-condition fix. Never launches inference or edits result files."""
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
a = p.parse_args()
target = Path(a.repo).resolve() / 'experiments/skill_lifecycle_r49.py'
old = 'if len(candidates)>5 and prescreen:'
new = 'if candidates and prescreen:'
text = target.read_text(encoding='utf-8')
if old not in text and new in text:
    print('Already applied:', target)
elif text.count(old) != 1:
    raise SystemExit('Expected retrieval condition not found exactly once; inspect local changes first.')
else:
    # Keep all local recovery changes; replace only the applicability gate trigger.
    updated = text.replace(old, new, 1)
    compile(updated, str(target), 'exec')
    backup = target.with_name(target.name + '.before_gate_fix')
    if backup.exists():
        raise SystemExit('Backup exists; inspect before applying again.')
    backup.write_text(text, encoding='utf-8')
    target.write_text(updated, encoding='utf-8')
    print('Applied; backup:', backup)
    print('No experiment started. Use a new run/output namespace for future inference.')
