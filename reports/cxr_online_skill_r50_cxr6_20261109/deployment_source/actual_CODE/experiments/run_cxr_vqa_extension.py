"""Select a first-phase arm with the existing resume and reservation machinery."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from cxr_vqa_official_medrax import OfficialMedRAX
from run_cxr_vqa_toolsets import agent_system, episode, main, read


def terms(text):
    return set(re.findall(r'[a-z]{3,}', text.lower()))


def conditioning_for(row, arm, runtime):
    if arm in ('D-H', 'M-H'):
        history = row.get('history') or {}
        if set(history) != {'age', 'sex', 'clinical_history'} or any(v is None or v=='' for v in history.values()):
            raise ValueError('History comparison requires all three independent fields')
        return 'Independently recorded clinical context:\n'+json.dumps(history, ensure_ascii=False)
    if arm not in ('M-S', 'M-E'):
        return None
    spec = runtime['arms'][arm]
    path = Path(spec['bank_path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['bank_sha256']:
        raise ValueError('Frozen source bank changed')
    bank = json.loads(raw)
    if bank['kind']!=arm or not bank['source_only'] or not bank['frozen']:
        raise ValueError('Invalid source bank')
    query = terms(row['question'])
    candidates = []
    for item in bank['items']:
        topic = terms(item['topic'])
        score = len(query & topic)/max(1,len(query | topic))
        if score:
            candidates.append((-score, item['source_id'], item['content']))
    selected = [x[2] for x in sorted(candidates,key=lambda x:x[:2])[:2]]
    if not selected:
        return None
    prefix = ('Source-derived optional skill checks' if arm=='M-S' else 'Related source-case experiences')
    return prefix+'. Check applicability to the current original and use only supported evidence.\n'+json.dumps(selected,ensure_ascii=False)


def run(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--arms', nargs='+', required=True)
    args, rest = parser.parse_known_args(argv)
    official = None
    if 'O' in args.arms:
        runtime = read(read(args.config)['runtime'])
        official = OfficialMedRAX(Path(runtime['official_checkout']))

    def dispatch(row, arm, data, protocol, runtime, out, paid, tools):
        if arm=='O':
            return official.episode(row, arm, data, protocol, runtime, out, paid, tools)
        conditioning = conditioning_for(row, arm, runtime)
        return episode(row, arm, data, protocol, runtime, out, paid, tools, conditioning=conditioning)

    def system(arm):
        return official.system if arm == 'O' else agent_system(arm)

    return main(['--config', str(args.config), '--arms', *args.arms, *rest],
                arms=('D', 'M', 'C', 'X', 'O', 'M-R', 'M-S', 'M-E', 'D-H', 'M-H'),
                episode_fn=dispatch, system_fn=system, extra_input_fields=('history',))


if __name__ == '__main__':
    raise SystemExit(run())
