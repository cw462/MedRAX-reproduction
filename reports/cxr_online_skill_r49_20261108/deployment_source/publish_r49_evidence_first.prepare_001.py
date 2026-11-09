"""User-directed evidence-first publication; the final-audit publisher is unchanged."""
import argparse
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

import publish_cxr_online_skill_r49 as pub
import finalize_r49_report as writer

pub.RECEIPTS = pub.ROOT / 'local_assets/r49_evidence_first_publication'


def preliminary_ready():
    result = {}
    for ds, spec in pub.DATASETS.items():
        evidence = pub.REPORT / 'evidence' / ds
        manifest = pub.read(evidence / 'publication_manifest.json')
        saved = pub.read(pub.REPORT / 'results' / ds / 'summary.json')
        exported = pub.read(evidence / 'scores/summary.json')
        if (manifest['scope'] != 'complete_scored_online_stream'
                or manifest['questions'] != spec['n'] or manifest['raw_generation_exit'] != 0
                or saved != exported or saved['questions'] != spec['n']
                or saved['arms'][spec['baseline']]['correct'] != spec['baseline_correct']):
            raise ValueError('complete_saved_result_and_public_export_required:' + ds)
        for name in ('controller', ds):
            if (evidence / 'job_records' / (name + '.exitcode')).read_text().strip() != '0':
                raise ValueError('actual_final_zero_required:' + ds)
        result[ds] = {'n': spec['n'], 'R49_correct': saved['arms'][pub.ARM]['correct'],
                      'publication_phase': 'user_requested_evidence_first',
                      'final_DeepSeek_audit_not_claimed': True}
    if not (pub.REPORT / 'evidence/recovery/publication_manifest.json').is_file():
        raise ValueError('all_preserved_recovery_history_required')
    return result


def prepare_documents():
    preliminary_ready()
    if (pub.REPORT / 'README.md').exists():
        raise ValueError('initial_report_already_written_do_not_overwrite')
    now = datetime.now(timezone.utc).isoformat()
    amendment = f'''# User-directed publication sequence amendment

Recorded {now}. The actual user first said “先上传github吧”, then “抓紧推送”. These instructions supersede the earlier order requiring the final DeepSeek review before the first upload. Publish the completed results and full exported evidence first, then finish public reproduction, the one new complete-results DeepSeek review, final report and follow-up publication. This changes publication order only; it does not claim that the deferred review happened.

All three generation streams, private scores and public exports are complete. Original predictions, references, native scoring semantics, failure records and the user's open_questions_for_later.jsonl are untouched. No inference, private rescoring, transfer or old review is repeated. The original final-audit publisher and its gates remain unchanged; the separate published evidence-first helper reuses its explicit allowlist, credential/link/file-size checks, ordinary commit/push and main verification with a truthful completed-evidence gate. No force, reset or merge is authorized. Expected initial main: 641746b8680c3b62d655abb154ab773cd57e6388. A subsequent final publication may advance only the verified commit created by this authorized first upload; any other remote change stops work.

The original adoption prelaunch audit_deferred_until_full_generation control remains historical and unchanged. This amendment is not a positive result review, clinical audit or model-weight attestation.
'''
    (pub.REPORT / 'PUBLICATION_SEQUENCE_AMENDMENT.md').write_text(amendment, encoding='utf-8')
    lines = ['# R49: completed results and public evidence', '',
             '**Evidence-first publication at the user’s explicit request. Final DeepSeek result/claim review and final report are pending.**', '',
             'All 848 question-level generations and three private scores completed. Scores below reuse the immutable saved results. This upload preserves negative findings, actual failures and recovery history. It does not assert that 848 questions are independent patients or cases.', '',
             '| Dataset | R49 | Historical whole arm | Corrected / harmed / net |',
             '|---|---:|---:|---:|']
    bundles = {}
    for ds, spec in pub.DATASETS.items():
        s = pub.read(pub.REPORT / 'results' / ds / 'summary.json'); bundles[ds] = {'summary': s}
        c = s['comparisons'][spec['baseline']]
        lines.append(f"| {ds} | {s['arms'][pub.ARM]['correct']}/{spec['n']} | {spec['baseline']} {spec['baseline_correct']}/{spec['n']} | {c['corrected']} / {c['harmed']} / {c['net']:+d} |")
    lines += ['', 'VQA-RAD uses M42: the M43 phase retained M42’s 100/116 and did not run a separate VQA arm. CheX R47 online-GT 468/618 remains a secondary comparator in its saved results.', '',
              'Final adoption_1 controller and all three original runners exited zero. Every initial/intermediate exit1 remains in the full recovery tree. No failed attempt is relabeled successful.', '',
              '## Evidence and current reproduction status', '']
    for ds in pub.DATASETS:
        q = pub.REPORT / 'public_reproduction' / ds / 'summary.json'
        status = 'completed: saved public scores, extractions and resources match' if q.is_file() else 'running; no completed public reproduction asserted'
        lines += [f"- **{ds}** — {status}. [Saved scores](results/{ds}/summary.json), [all question-level results](results/{ds}/per_question.json), [questions/options/images/requests/replies/tools/feedback/Skills](evidence/{ds}/), [evidence manifest](evidence/{ds}/publication_manifest.json)."]
    lines += ['', '[Full failure and recovery evidence](evidence/recovery/) · [Executed code and helper provenance](deployment_source/PROVENANCE.md) · [Protocol](PROTOCOL.json) · [Method and limitations](METHOD_AND_LIMITS.md) · [Actual test history](TESTS.md) · [Publication sequence amendment](PUBLICATION_SEQUENCE_AMENDMENT.md).', '',
              '## Interpretation and resource limits', '',
              'This is an exposed online dataset-ground-truth feedback experiment with unrestricted request budgets, changed executor/sampling/time/prompts/EOS policy and mixed legacy caches. It has no simultaneous no-Skill control. Skill hits are 505/618, 0/114, 0/116; same-image memory hits are 130/618, 84/114, 58/116. SLAKE and CheX-SLAKE share 17 images / 64 matched questions; VQA paraphrases cluster by image. No Skill-only causality, equal-budget gain, closed-test SOTA or medical capability is claimed.', '',
              'Each saved score summary contains complete per-category resources, known token/time/CNY usage proxies, failed production attempts and separately reported diagnostics. Missing provider usage/cost, hardware prices and full controller wall time stay unknown. CLI review USD estimates are separate from inference CNY proxies and are not provider invoices. Archived duplicate copies of a request are not additional charges.', '',
              'The original execution/repair reviews cover their own historical scopes. A new final complete-results review has not yet been dispatched at preparation of this first upload. Final findings and a complete report will follow in a later commit; no favorable verdict is prewritten.', '']
    (pub.REPORT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    text = '\n\n'.join(writer.sentence(ds, bundles[ds]['summary']) for ds in pub.DATASETS)
    for relative in pub.INDEXES:
        dest = pub.ROOT / relative
        target = '../cxr_online_skill_r49_20261108/README.md' if relative.startswith('reports/') else pub.REPORT_REL + '/README.md'
        block = '**R49 completed results: evidence-first publication; final result review pending.**\n\n' + text + '\n\nOnline GT and executor/resource/prompt confounds prevent Skill-only causal or SOTA claims. [Full public evidence](' + target + ').'
        dest.write_text(writer.replace_block(dest, block), encoding='utf-8')
    shutil.copyfile(__file__, pub.REPORT / 'deployment_source/publish_r49_evidence_first.py')
    (pub.REPORT / 'deployment_source/EVIDENCE_FIRST_SOURCE_NOTE.md').write_text(
        '# Evidence-first publication helper\n\nThe sibling publish_r49_evidence_first.py is the actual local helper added after the original 293-copy source preparation in response to the user’s explicit request to upload first. It changes publication order, preserves the original final-audit publisher unchanged and does not fabricate a completed review. No source hash or new experiment is asserted.\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['prepare', 'check', 'stage', 'commit-push', 'verify'])
    args = p.parse_args(); args.expected_base = pub.EXPECTED_BASE
    args.include_untracked_originals = False
    args.message = 'Publish completed R49 results and full evidence before final review at user request'
    pub.ready = preliminary_ready
    if args.mode == 'prepare':
        prepare_documents()
    {'prepare': pub.prepare, 'check': pub.check, 'stage': pub.stage,
     'commit-push': pub.commit_push, 'verify': pub.verify}[args.mode](args)
