"""Run a single frozen full-cohort R55 D or EvolveR dataset.

The scheduler supplies a manifest built from the original full D dataset
inputs, order and reference index. EvolveR consumes that same manifest shape
with an independent writer and experience bank for each dataset.
"""

import argparse
import json
from pathlib import Path
import sys


ARMS = {'D': 'M43-IM-GT-T55-D', 'E': 'R55-E-EvolveR'}
COUNTS = {'chexbench': 618, 'slake': 114, 'vqarad': 116}


class PrefixVerified(Exception):
    """Stop before the first new model request during an offline replay."""


def run_dataset(code, out, data, references, arm, verify_prefix):
    sys.path.insert(0, str(code/'experiments'))
    from cxr_online_primitives_r49 import rows
    from online_memory_r49 import ReferenceVault, read
    from run_cxr_vqa_toolsets import exclusive_lock

    m = read(out/'manifest.json')
    inputs, order = m['inputs'], m['order']
    ids = [row['question_id'] for row in inputs]
    tools = m['runtime']['arms']['M']['tools']
    assert len(ids) == len(set(ids)) == COUNTS[m['dataset']]
    assert rows(data/'inputs.jsonl') == inputs
    assert [row['question_id'] for row in order] == ids
    assert set(m['reference_files']) == set(ids) and len(tools) == 11
    assert m['arm'] == ARMS[arm] and m['skill_enabled'] == (arm == 'E')

    if arm == 'D':
        import run_online_skill_r54 as engine
        from skill_services_r55 import Services
        flags = {'evolver': engine.disabled_evolve}
    else:
        import run_online_evolver_shared as engine
        from r55_unvalidated_experience import evolve
        from skill_services_evolver_shared import Services
        assert m['experience_admission'] == 'returned_text_without_validation'
        flags = {'evolver': evolve, 'route': 'experience'}
    engine.ARM = ARMS[arm]

    if verify_prefix is not None:
        assert 0 <= verify_prefix < len(inputs)
        saved = out/'predictions'/ARMS[arm]
        assert {path.stem for path in saved.glob('*.json')} == set(ids[:verify_prefix])

        class StopBeforeSend:
            def set_candidates(self, selected):
                assert not selected

            def execute(self, row, *_):
                assert row == inputs[verify_prefix]
                raise PrefixVerified

        service = StopBeforeSend()
    else:
        key = sys.stdin.readline().strip()
        assert key
        extra = {'writer': m['writer']} if arm == 'E' else {}
        service = Services(m['config'], m['protocol'], m['runtime'], out/'services',
                           key, m['embedding_model'], m['embedding_base_url'], **extra)

    try:
        with exclusive_lock(out/'.online.lock'):
            engine.run_stream(inputs, order, data, out, service,
                              ReferenceVault(references, m['reference_files']),
                              tools, **flags)
    except PrefixVerified:
        assert verify_prefix is not None
        return {'arm': arm, 'dataset': m['dataset'], 'verified_prefix': verify_prefix,
                'first_new': ids[verify_prefix], 'model_requests': 0}

    assert verify_prefix is None
    done = read(out/'complete.json')
    assert done['questions'] == COUNTS[m['dataset']] and done['arm'] == ARMS[arm]
    return {'arm': arm, 'dataset': m['dataset'], 'questions': done['questions']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=tuple(ARMS), required=True)
    for name in ('code', 'out', 'data', 'references'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--verify-prefix', type=int)
    args = parser.parse_args()
    print(json.dumps(run_dataset(args.code, args.out, args.data, args.references,
                                 args.arm, args.verify_prefix)))
