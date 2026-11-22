"""Stage R55 ReAct, CRITIC and Reflexion with the frozen eight-tool menu."""

import json
from pathlib import Path


ENTRY = 'run_qwen_baselines.py'
AGENTS = 'r55_baselines_8tools.py'


def _replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Unexpected R55 baseline source near {old.splitlines()[0]}')
    return source.replace(old, new, 1)


def _write_code(path, source):
    compile(source, str(path), 'exec')
    path.write_text(source, encoding='utf-8')


def _link(path, source):
    source = source.resolve(strict=True)
    if not path.is_symlink() and not path.exists():
        path.symlink_to(source, target_is_directory=source.is_dir())
    if path.resolve() != source:
        raise ValueError(f'Unexpected baseline binding for {path}')


def _read(path):
    return json.loads(path.read_bytes())


def _predictions(path, method, question_ids):
    files = {file.stem: file for file in (path / 'predictions').glob('*.json')}
    if set(files) != question_ids:
        raise ValueError(f'Incomplete frozen {method} cohort at {path}')
    for qid, file in files.items():
        record = _read(file)
        if (record['arm'], record['question_id']) != (method, qid):
            raise ValueError(f'Wrong frozen {method} prediction {file}')


REPLAY = '''
def replay_trial(session, row, saved):
    qid = row['question_id']
    record = json.loads(saved.read_bytes())
    if (record['arm'], record['question_id']) != ('react', qid):
        raise ValueError(f'ReAct replay identity mismatch for {qid}')
    model = session.manifest['protocol']['model']
    archive = session.out / 'replay' / session.dataset
    if model == 'deepseek-flash':
        from r55_deepseek_official import matches

        archive = session.api_dir
        ordinal = str(record['calls']['qwen'])
        request = None
        for role in ('react', 'react_request_retry1', 'react_request_retry2'):
            folder = archive / 'calls' / role / qid / ordinal
            receipt = folder / 'result.json'
            if not receipt.is_file():
                continue
            result = json.loads(receipt.read_bytes())
            if result['response_received']:
                response = json.loads((folder / 'response.json').read_bytes())
                raw = response['choices'][0]['message'].get('content') or ''
                if not matches(result['model_returned']) or raw != record['raw']:
                    raise ValueError(f'DeepSeek ReAct replay response mismatch for {qid}')
                request = json.loads((folder / 'request.json').read_bytes())
                break
        if request is None:
            raise ValueError(f'Missing completed DeepSeek ReAct request for {qid}')
    else:
        archived = json.loads((archive / f'{qid}.json').read_bytes())
        result = archived['result']
        if not result['response_received'] or result['model_returned'] != model or int(archived['ordinal']) != record['calls']['qwen']:
            raise ValueError(f'Historical ReAct response mismatch for {qid}')
        request = archived['request']
    if request['model'] != model:
        raise ValueError(f'ReAct replay model mismatch for {qid}')
    messages = request['messages']
    for message in messages:
        if isinstance(message['content'], str):
            continue
        for part in message['content']:
            if part['type'] != 'image_url':
                continue
            url = part['image_url']['url']
            if isinstance(url, dict):
                digest = url['cxr_request_image_base64_sha256']
                encoded = (archive / 'request_image_base64' / digest).read_text(encoding='ascii')
                part['image_url']['url'] = f"data:{url['media_type']};base64,{encoded}"
    return record['raw'], record['calls'], messages


'''


def _runner(source):
    source = _replace(
        source,
        '        from r55_qwen8_runtime import wait_for_case\n        wait_for_case()\n',
        "        from r55_deepseek_rerun_runtime import wait_for_arm\n"
        "        wait_for_arm(self.root.parent, os.environ['R55_QWEN8_ARM'])\n",
    )
    source = _replace(
        source,
        "    if args.r55_8_tools and args.method == 'react' and args.dataset != 'chexbench':\n"
        "        lock_name = f'{args.method}.{args.dataset}.lock'\n",
        "    if args.r55_8_tools:\n        lock_name = f'{args.method}.{args.dataset}.lock'\n",
    )
    source = _replace(source, 'The existing Qwen credential must be supplied through stdin',
                      'The main-model credential must be supplied through stdin')
    source = _replace(source, '--wait-for-react applies to the 11-tool Reflexion run',
                      '--wait-for-react applies to the eight-tool Reflexion run')
    source = _replace(
        source,
        "            'critic_initial_answer': 'reuse frozen CoT prediction when available',\n",
        "            'critic_initial_answer': 'same-model tool-free CoT captured before evidence checks',\n"
        "            'reflexion_first_trial': 'paired same-model eight-tool ReAct when requested',\n",
    )
    return _replace(
        source,
        '                if status not in (408, 429, 500, 502, 503, 504) and not match:',
        "                transport_failed = receipt.get('error') in ('Request timed out.', 'Connection error.')\n"
        '                if status not in (408, 429, 500, 502, 503, 504) and not match and not transport_failed:',
    )


def _agent(source):
    source = _replace(source, 'from r55_qwen8_runtime import TOOLS as TOOL_MENU',
                      'from r55_run_plan import TOOLS as TOOL_MENU')
    source = _replace(source, 'class R55Baselines(Baselines):\n', REPLAY + 'class R55Baselines(Baselines):\n')
    source = _replace(
        source,
        "                raise RuntimeError('Reflexion needs its completed ReAct first trial')\n"
        '        return self.evidence_loop(row, arm, messages)\n',
        "                raise RuntimeError('Reflexion needs its completed ReAct first trial')\n"
        '            return replay_trial(self, row, saved)\n'
        '        return self.evidence_loop(row, arm, messages)\n',
    )
    return _replace(
        source,
        "        if not prior.is_file():\n            raise ValueError('Missing frozen CoT candidate for CRITIC.')\n",
        "        if not prior.is_file():\n"
        "            if self.manifest['protocol']['model'] != 'deepseek-flash':\n"
        "                raise ValueError('Missing frozen Qwen CoT candidate for CRITIC.')\n"
        "            self.predict(row, 'cot')\n",
    )


def stage(root: Path, prior8: Path, official: Path, datasets: dict):
    """Install production baseline sources and bind the frozen trial inputs."""
    prior_source = prior8 / 'flash/flash_react/code'
    tools = _read(root / 'plan.json')['tools']
    _write_code(root / 'bin/r55_run_plan.py', f'TOOLS = {tuple(tools)!r}\n')
    base = prior8.parent
    cot_roots = {
        'flash': base / 'qwen36_flash_cot_20261115_001/cot',
        'plus': base / 'cot_repeat_20261115_001/cot',
        'deepseek': official / 'flash_react/cot',
    }
    status = {}
    for variant, cot_source in cot_roots.items():
        model_root = root / variant
        out = model_root / 'flash_react'
        code = out / 'code'
        code.mkdir(parents=True, exist_ok=True)
        (out / 'api').mkdir(exist_ok=True)
        (out / 'cot').mkdir(exist_ok=True)
        for name in ('r55_baseline_common.py', 'r55_baseline_vqa.py', 'run_chexagent8_direct.py'):
            _link(code / name, prior_source / name)
        _write_code(code / ENTRY, _runner((prior_source / ENTRY).read_text(encoding='utf-8')))
        _write_code(code / AGENTS, _agent((prior_source / AGENTS).read_text(encoding='utf-8')))
        status[variant] = {}
        previous = prior8 / variant / 'flash_react'
        if variant != 'deepseek':
            original_protocol = _read(previous / 'react.protocol.json')
            if original_protocol['tool_menu'] != tools:
                raise ValueError(f'Historical {variant} ReAct has the wrong tool menu')
            _link(out / 'react', previous / 'react')
        for ds, n in datasets.items():
            manifest = _read(model_root / 'manifests/ReAct' / f'{ds}.json')
            ids = {row['question_id'] for row in manifest['inputs']}
            if len(ids) != n or set(manifest['runtime']['tools']) != set(tools):
                raise ValueError(f'Unexpected {variant} {ds} baseline cohort')
            if variant != 'deepseek':
                prior_manifest = _read(prior8 / variant / 'manifests/ReAct' / f'{ds}.json')
                if original_protocol['model'] != manifest['protocol']['model'] or any(
                    prior_manifest[field] != manifest[field] for field in ('inputs', 'order', 'reference_files')
                ):
                    raise ValueError(f'Historical {variant} {ds} ReAct input or model mismatch')
                _predictions(out / 'react' / ds, 'react', ids)
            cot = out / 'cot' / ds
            historical = cot_source / ds
            if variant != 'deepseek' or ds == 'slake':
                _predictions(historical, 'cot', ids)
                _link(cot, historical)
            elif (cot / 'predictions').is_dir():
                _predictions(cot, 'cot', ids)
            status[variant][ds] = {
                'paired_react_predictions': n if variant != 'deepseek' else 0,
                'cot_predictions': len(list((cot / 'predictions').glob('*.json'))),
            }
    return status
