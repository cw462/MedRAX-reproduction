"""R55 D/E entry point using the original R54 stream and S54 lifecycle."""

import argparse
import sys
from pathlib import Path

import run_online_skill_r54 as r54
from r55_verifier import BASE_URL, CREDENTIAL_SLOT, profile as verifier_profile
from skill_services_r55 import NEW_TOOLS, Services, UPSTREAM_COMMIT

COUNTS = {'chexbench': 618, 'slake': 114, 'vqarad': 116}


def prepare(args, cfg, runtime):
    if args.expect_questions != COUNTS[args.dataset]:
        raise ValueError('R55_requires_original_cohort_size')
    if args.dataset == 'chexbench' and args.order_manifest is None:
        raise ValueError('R55_requires_original_R54_CheXBench_order_manifest')
    if (cfg['model'], cfg['temperature'], cfg['top_p'], cfg['max_output_tokens'],
            cfg.get('extra_body', {}).get('enable_thinking')) != ('qwen3.7-plus', 0.2, 0.95, 2048, False):
        raise ValueError('R55_requires_shared_R54_model_settings')
    if (cfg.get('credential_slot'), cfg['profile']['base_url'].rstrip('/')) != (CREDENTIAL_SLOT, BASE_URL):
        raise ValueError('R55_requires_shared_Model_Studio_Token_Plan_entry')
    arm = 'E' if args.skill == 'on' else 'D'
    for name, (backend, description) in NEW_TOOLS.items():
        runtime['tools'][name] = {'backend': backend, 'description': description,
                                  'revision': 'SkeMex@' + UPSTREAM_COMMIT}
    for spec in runtime['arms'].values():
        spec['tools'] = [*spec['tools'], *NEW_TOOLS]
    return 'M43-IM-GT-T55-' + arm, runtime


def manifest_metadata():
    return {
        'schema': 'r55_de_online_v1',
        'implementation_revision': 'R55.DE.3',
        'new_tool_source': {'repository': 'https://github.com/manglu097/SkeMex',
                            'commit': UPSTREAM_COMMIT, 'bindings': {
                                name: value[0] for name, value in NEW_TOOLS.items()}},
        'new_tool_model_policy': {'reflect': 'qwen3.7-plus', 'medret_synthesis': 'qwen3.7-plus',
                                  'verify': verifier_profile()},
        'verify_inputs': ['original_images', 'complete_options', 'candidate', 'risk',
                          'prior_same_case_medret_evidence'],
        'skill_lifecycle': 'original_R54_S54',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False, allow_abbrev=False)
    parser.add_argument('--arm', required=True, choices=('D', 'E'))
    parser.add_argument('--dataset', required=True, choices=tuple(COUNTS))
    parser.add_argument('--out', required=True, type=Path, help='common R55 output root')
    args, remaining = parser.parse_known_args(argv)
    if any(token.split('=', 1)[0] in ('--skill', '--expect-questions') for token in remaining):
        parser.error('R55 derives --skill and --expect-questions from --arm and --dataset')
    skill = 'on' if args.arm == 'E' else 'off'
    r54.main([*remaining, '--skill', skill, '--dataset', args.dataset,
              '--expect-questions', str(COUNTS[args.dataset]),
              '--out', str(args.out / args.arm / args.dataset)], variant=sys.modules[__name__])


if __name__ == '__main__':
    main()
