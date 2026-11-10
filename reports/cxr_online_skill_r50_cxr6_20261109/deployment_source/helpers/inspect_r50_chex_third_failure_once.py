"""Single-use bounded capture of the new recovery002 stop after 316 predictions."""
import json
from datetime import datetime, timezone
from deploy_cxr6_r50 import connect, RUN, ARM, PREP

DEST = PREP / 'failures/003_chex_316'


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    files = []

    def put(name, value):
        with (DEST / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')

    put('inspection.started.json', {
        'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'new stopped question/cache/recovery002 jobs only; no labels or model calls',
    })
    try:
        with connect() as client, client.open_sftp() as s:
            def capture(relative):
                path = DEST / 'originals' / relative
                if path.exists():
                    return path
                path.parent.mkdir(parents=True, exist_ok=True)
                info = s.stat(RUN + '/' + relative)
                with s.open(RUN + '/' + relative, 'rb') as a, path.open('xb') as b:
                    while True:
                        body = a.read(1024 * 1024)
                        if not body:
                            break
                        b.write(body)
                files.append({'relative': relative, 'remote_size': info.st_size, 'remote_mtime': info.st_mtime})
                return path

            def parsed(relative):
                return json.loads(capture(relative).read_text(encoding='utf-8'))

            for job in ('controller_recovery002', 'chexbench_recovery002'):
                for suffix in ('.log', '.pid', '.exitcode'):
                    p = capture('jobs/' + job + suffix)
                    if suffix == '.exitcode' and p.read_text().strip() != '1':
                        raise ValueError('new_failed_job_raw_exit_must_be_1')
            capture('jobs/queue_status.recovery002.json')
            base = 'generation/chexbench/'
            for name in ('generation.exitcode', 'generation.recovery001.exitcode', 'generation.recovery002.exitcode'):
                if capture(base + name).read_text().strip() != '1':
                    raise ValueError('all_three_actual_failed_generation_exits_must_remain_1')
            preds = {x[:-5] for x in s.listdir(RUN + '/' + base + 'predictions/' + ARM) if x.endswith('.json')}
            contexts = {x[:-5] for x in s.listdir(RUN + '/' + base + 'contexts') if x.endswith('.json')}
            pending = contexts - preds
            if len(preds) != 316 or len(pending) != 1:
                raise ValueError('unexpected_third_failure_prefix')
            q = pending.pop()
            feedback_names = {x[:-5] for x in s.listdir(RUN + '/' + base + 'feedback') if x.endswith('.json')}
            if len(feedback_names) != 316 or q in feedback_names:
                raise ValueError('failed_question_own_feedback_must_be_absent')
            ctx = parsed(base + 'contexts/' + q + '.json')
            if ctx['ordinal'] != 317:
                raise ValueError('unexpected_failed_question_ordinal')
            for ordinal in s.listdir(RUN + '/' + base + 'services/calls/R50-AGENT/' + q):
                relative = base + 'services/calls/R50-AGENT/' + q + '/' + ordinal
                for name in s.listdir(RUN + '/' + relative):
                    capture(relative + '/' + name)
            selections = []
            for name in s.listdir(RUN + '/' + base + 'services/tool_selections/R50-AGENT/' + q):
                relative = base + 'services/tool_selections/R50-AGENT/' + q + '/' + name
                record = parsed(relative)
                if record.get('status') != 'completed':
                    selections.append({'relative': relative, 'record': record})
            if len(selections) != 1:
                raise ValueError('exact_new_failed_selection_required')
            failure = selections[0]
            cache = base + 'services/tool_cache/' + failure['record']['cache_key']
            for name in s.listdir(RUN + '/' + cache):
                if name != 'artifacts':
                    capture(cache + '/' + name)
            value = {'question_id': q, 'ordinal': ctx['ordinal'], 'saved_prefix': 316,
                     'failed_selection': failure, 'tool_cache': cache,
                     'original_and_both_prior_generation_exits_retained': True,
                     'failed_question_has_no_saved_prediction': q not in preds,
                     'failed_question_has_no_own_feedback': q not in feedback_names}
            put('actual_failure.json', value)
        put('inspection.completed.json', {'status': 'completed', 'utc': datetime.now(timezone.utc).isoformat(),
                                          'files': files, 'count': len(files), 'new_model_score_or_mutation_calls': 0})
        cache_dir = DEST / 'originals' / cache
        print(json.dumps({'failure': value, 'backend_original_tails': {
            p.name: p.read_text(encoding='utf-8', errors='replace').splitlines()[-90:]
            for p in cache_dir.glob('*.log')}, 'captured_original_files': len(files)}, ensure_ascii=False))
    except BaseException as exc:
        put('inspection.failure.json', {'utc': datetime.now(timezone.utc).isoformat(),
                                        'error_type': type(exc).__name__, 'error': str(exc), 'partial_files': files})
        raise


if __name__ == '__main__':
    main()
