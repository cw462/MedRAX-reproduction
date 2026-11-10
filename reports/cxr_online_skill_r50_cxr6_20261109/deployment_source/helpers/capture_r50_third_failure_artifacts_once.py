"""Read-only once capture of the already-generated MAIRA failure artifacts."""
import json
from datetime import datetime, timezone
from deploy_cxr6_r50 import connect, RUN, PREP

DEST = PREP / 'failures/003_chex_316'
BASE = 'generation/chexbench/services/tool_cache/65e65ea9f529a7ce811f54147a7c2326bf115aeaf0ddb2960ff9c3437d77626d/artifacts'


def main():
    def put(name, value):
        with (DEST / name).open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')

    put('artifact_capture.started.json', {'utc': datetime.now(timezone.utc).isoformat(),
                                        'scope': 'only existing failed MAIRA artifacts; no execution or labels'})
    files = []
    try:
        with connect() as client, client.open_sftp() as s:
            for entry in s.listdir_attr(RUN + '/' + BASE):
                name = entry.filename
                if '/' in name or '\\' in name or name in ('.', '..'):
                    raise ValueError('unsafe_artifact_name')
                relative = BASE + '/' + name
                target = DEST / 'originals' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with s.open(RUN + '/' + relative, 'rb') as src, target.open('xb') as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                files.append({'relative': relative, 'remote_size': entry.st_size, 'remote_mtime': entry.st_mtime})
        put('artifact_capture.completed.json', {'utc': datetime.now(timezone.utc).isoformat(),
                                              'status': 'completed', 'files': files, 'count': len(files),
                                              'new_model_score_or_mutation_calls': 0})
        folder = DEST / 'originals' / BASE
        def read(name):
            return json.loads((folder / name).read_text(encoding='utf-8'))
        original = read('original_worker_result.json')
        gens = read('generation_tokens.json')
        print(json.dumps({'original_worker_result': original,
                          'policy_status': read('policy_status.json'),
                          'generations': [{k: v for k, v in g.items() if k not in ('output_token_ids', 'generated_token_ids')} |
                                          {'generated_lengths': [len(row) for row in g['generated_token_ids']],
                                           'last_12_generated_tokens': [row[-12:] for row in g['generated_token_ids']]} for g in gens],
                          'decode': read('decode.json'), 'swallowed_exceptions': read('swallowed_exceptions.json'),
                          'observability_errors': read('observability_errors.json'),
                          'copied_files': len(files)}, ensure_ascii=False))
    except BaseException as exc:
        put('artifact_capture.failure.json', {'utc': datetime.now(timezone.utc).isoformat(),
                                            'error_type': type(exc).__name__, 'error': str(exc), 'partial_files': files})
        raise


if __name__ == '__main__':
    main()
