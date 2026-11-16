"""Archive the completed AutoDL M14 runs and publish their paired results."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from deploy import HERE, MODELS, RUN, connect, execute


REPO = HERE.parents[1]
ARCHIVE = Path('H:/MedRAX_Experiment_Artifacts') / RUN
REPORT = 'reports/r55_gsem_openi60_autodl_20261116'
BRANCH = 'refs/heads/reports/r55-gsem-openi60-autodl-20261116'
REMOTE = 'https://github.com/cw462/MedRAX-reproduction.git'
LABELS = {'qwen36': 'Qwen3.6-Flash', 'deepseek41': 'DeepSeek V4.1 Flash'}
ARM = 'R55-M14-GSEM'
TOKEN = re.compile(r'\b(?:sk|rk|pk)-[\w-]{16,}|\bBearer\s+[\w.-]{16,}', re.I)
COMPACT = r'''
from pathlib import Path
import sys, tarfile
root, label = Path(sys.argv[1]), sys.argv[2]
if label == 'frozen-setup':
    files = [root / n for n in ('gsem_memory.py', 'run_pilot.py', 'test_gsem.py', 'initial_graph.json', 'stage.json')]
    files.extend(root / 'code/experiments' / n for n in ('autodl_services.py', 'run_online_skill_r54.py',
        'skill_services_r55.py', 'toolsets_r54.py', 'tool_worker_r54.py', 'r55_resident_tools.py'))
else:
    root = root / label
    files = [root / n for n in ('per_question.json', 'score.json', 'exitcode', 'generation/manifest.json')]
    for pattern in ('predictions/*/*.json', 'steps/*.json', 'external_memory/episodes/*/*.json',
                    'services/calls/*/*/*/result.json'):
        files.extend((root / 'generation').glob(pattern))
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as tar:
    for f in files:
        tar.add(f, arcname=f.relative_to(root).as_posix(), recursive=False)
'''


def store(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.pending')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def fetch_tar(ssh, directory, names, destination):
    if destination.is_file():
        return
    run_root = directory.parent if directory.name in (*MODELS, 'chexbench') else directory
    if directory.name == 'chexbench':
        run_root = directory.parent.parent / RUN
    spool = run_root / ('.archive-' + destination.name)
    pending = spool.with_suffix('.pending')
    command = shlex.join(['tar', '-czf', str(pending), '-C', str(directory), '--', *names])
    command += ' && ' + shlex.join(['mv', '--', str(pending), str(spool)])
    command = shlex.join(['test', '-s', str(spool)]) + ' || (' + command + ')'
    stdin, stdout, stderr = ssh.exec_command(command, timeout=50)
    stdin.channel.shutdown_write()
    stdout.read()
    errors = stderr.read()
    if stdout.channel.recv_exit_status():
        raise RuntimeError(errors.decode(errors='replace')[-1300:])
    with ssh.open_sftp() as sftp:
        sftp.get_channel().settimeout(30)
        size = sftp.stat(str(spool)).st_size
    work = ARCHIVE / (destination.stem + '.transfer')
    work.mkdir(exist_ok=True)
    sys.path.insert(0, str(REPO / '.aris'))
    from r55_publish_deepseek41_rerun import download_spool
    downloaded, temporary = download_spool(work, {'path': str(spool), 'bytes': size, 'token': 'gsem'})
    downloaded.replace(destination)
    for p in temporary:
        p.unlink(missing_ok=True)
    if temporary:
        (work / 'ranges.gsem').rmdir()
    work.rmdir()
    with ssh.open_sftp() as sftp:
        sftp.remove(str(spool))


def archive(state):
    root = PurePosixPath(state['root'])
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    runs = ['generation', 'per_question.json', 'score.json', 'started.json', 'exitcode', 'stdout.log', 'stderr.log',
            'attempt-before-auxiliary-link']
    setup = ['gsem_memory.py', 'run_pilot.py', 'test_gsem.py', 'accepted.private.json', 'initial_graph.json',
             'auxiliary.json', 'lab-manifest.json', 'stage.json', 'code']
    with connect() as ssh:
        for label, result in state['arms'].items():
            if result['exit'] == 0 and result['saved'] == result['ingested'] == 60:
                fetch_tar(ssh, root / label, runs, ARCHIVE / f'{label}.tar.gz')
        fetch_tar(ssh, root, setup, ARCHIVE / 'frozen-setup.tar.gz')
        with tarfile.open(ARCHIVE / 'frozen-setup.tar.gz') as source:
            m = json.load(source.extractfile('lab-manifest.json'))
        images = sorted({name for row in m['inputs'] for name in row['images']})
        if len(images) != 60 or not all(PurePosixPath(p).parent.as_posix() == 'images/openi/images' for p in images):
            raise ValueError('Unexpected OpenI image membership')
        fetch_tar(ssh, root.parent / 'data/chexbench', images, ARCHIVE / 'original-openi.tar.gz')


def archive_report(state):
    out = ARCHIVE / 'report-evidence'
    out.mkdir(parents=True, exist_ok=True)
    with connect() as ssh:
        for label in (*MODELS, 'frozen-setup'):
            path = out / f'{label}.tar.gz'
            if path.is_file():
                continue
            args = ['/root/miniconda3/bin/python', '-B', '-c', COMPACT, state['root'], label]
            stdin, stdout, stderr = ssh.exec_command(shlex.join(args), timeout=35)
            stdin.channel.shutdown_write()
            tmp = path.with_suffix('.pending')
            with tmp.open('wb') as target:
                shutil.copyfileobj(stdout, target, length=32768)
            errors = stderr.read()
            if stdout.channel.recv_exit_status():
                raise RuntimeError(errors.decode(errors='replace')[-1300:])
            tmp.replace(path)
    return out


def scrub(value):
    if isinstance(value, str):
        value = TOKEN.sub('[redacted]', value)
        if value.startswith('data:image/'):
            return '[image saved as an artifact]'
        if value.startswith(('/root/', '/home/')):
            return PurePosixPath(value).name
        return value
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k.lower() not in ('api_key', 'authorization')}
    return value


def copy_member(tar, member, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    with tar.extractfile(member) as inp, out.open('wb') as dst:
        shutil.copyfileobj(inp, dst)


def read_arm(label, state, release, evidence):
    path = evidence / f'{label}.tar.gz'
    docs, episodes, images = {}, set(), {}
    tool_and_model_receipts, usage = Counter(), Counter()
    wanted = {'per_question.json', 'score.json', 'generation/manifest.json'}
    exit_code = None
    with tarfile.open(path, mode='r|gz') as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name
            artifact = PurePosixPath(name)
            if name == 'exitcode':
                exit_code = int(tar.extractfile(member).read())
            elif name.startswith('generation/external_memory/episodes/'):
                episodes.add(name)
            elif name.startswith('generation/services/calls/') and name.endswith('/result.json'):
                result = json.load(tar.extractfile(member))
                tool_and_model_receipts[(artifact.parts[3], str(result.get('model_returned')))] += 1
                for k in ('prompt_tokens', 'completion_tokens'):
                    usage[k] += (result.get('usage') or {}).get(k) or 0
            elif (name.startswith('generation/services/tool_cache/') and artifact.suffix.lower() in
                  ('.png', '.jpg', '.jpeg') and '..' not in artifact.parts):
                out = Path('images/derived') / label / Path(*artifact.parts[3:])
                copy_member(tar, member, release / out)
                images[name] = out.as_posix()
            elif name in wanted or (artifact.suffix == '.json' and name.startswith(
                    (f'generation/predictions/{ARM}/', 'generation/steps/'))):
                docs[name] = json.load(tar.extractfile(member))
    rows, score, m = (docs[name] for name in ('per_question.json', 'score.json', 'generation/manifest.json'))
    ids = {row['question_id'] for row in rows}
    status = state['arms'][label]
    if (len(ids) != 60 or score != status['score'] or sum(r['correct'] for r in rows) != score['correct']
            or exit_code != 0 or set(status['model_replies']) != {m['config']['model']}):
        raise ValueError(f'{label} score or route differs from the verified native result')
    for row in rows:
        q = row['question_id']
        if any(f'generation/external_memory/episodes/{q}/{name}.json' not in episodes
               for name in ('retrieval', 'ingest')):
            raise ValueError(f'{label} is missing GSEM receipts for {q}')
        prediction = docs[f'generation/predictions/{ARM}/{q}.json']
        row['steps'] = docs[f'generation/steps/{q}.json']
        row['observations'] = prediction['observations']
        for observation in prediction['observations']:
            derived = []
            for original in observation.get('derived_images') or []:
                if isinstance(original, str):
                    name = original.partition('/generation/services/tool_cache/')[2]
                    if saved := images.get('generation/services/tool_cache/' + name):
                        derived.append(saved)
            observation['derived_images'] = derived
        row['original_images'] = []
        for name in row.pop('images'):
            source = 'https://openi.nlm.nih.gov/detailedresult?' + urlencode({'img': PurePosixPath(name).stem})
            image = {'source': source, 'name': PurePosixPath(name).name}
            if evidence == ARCHIVE:
                image['file'] = f"images/original/{image['name']}"
            row['original_images'].append(image)
    info = {'score': score, 'model': m['config']['model'], 'profile': m['config']['profile'],
            'protocol': m['protocol'], 'model_routes': [
                {'role': role, 'model_returned': model, 'receipts': n}
                for (role, model), n in sorted(tool_and_model_receipts.items())],
            'resident_requests': status['resident_calls'], 'usage': dict(usage),
            'seconds_to_last_prediction': status['latest_prediction_epoch'] - status['started_epoch'],
            'archive_bytes': path.stat().st_size, 'native_exit': 0, 'tool_models': m['new_tool_model_policy']}
    return rows, info


def render(state, release, evidence):
    results = {}
    runs = {}
    for label in MODELS:
        runs[label], results[label] = read_arm(label, state, release, evidence)
    left, right = (runs[m] for m in MODELS)
    pair = {'qwen_only_correct': [], 'deepseek_only_correct': [], 'both_correct': [], 'both_wrong': []}
    for a, b in zip(left, right, strict=True):
        if any(a[k] != b[k] for k in ('ordinal', 'question_id', 'question', 'options', 'reference', 'original_images')):
            raise ValueError('AutoDL arms do not match on their scored question protocol')
        kind = { (True, False): 'qwen_only_correct', (False, True): 'deepseek_only_correct',
                 (True, True): 'both_correct', (False, False): 'both_wrong' }[a['correct'], b['correct']]
        pair[kind].append(a['question_id'])
    with tarfile.open(evidence / 'frozen-setup.tar.gz') as source:
        stage = json.load(source.extractfile('stage.json'))
        graph = json.load(source.extractfile('initial_graph.json'))
        for name in ('gsem_memory.py', 'run_pilot.py', 'test_gsem.py', 'code/experiments/autodl_services.py',
                     'code/experiments/run_online_skill_r54.py', 'code/experiments/skill_services_r55.py',
                     'code/experiments/toolsets_r54.py', 'code/experiments/tool_worker_r54.py',
                     'code/experiments/r55_resident_tools.py'):
            copy_member(source, name, release / 'source' / PurePosixPath(name).name)
    for name in ('deploy.py', 'remote.py', 'finalize.py'):
        shutil.copy2(HERE / name, release / 'source' / name)
    if evidence == ARCHIVE:
        with tarfile.open(evidence / 'original-openi.tar.gz') as source:
            for member in source:
                copy_member(source, member, release / 'images/original' / PurePosixPath(member.name).name)
    for card in graph['cards']:
        for key in ('split_keys', 'donor_cases', 'source'):
            card.pop(key, None)
    summary = {'arms': results, 'paired': pair, 'stage': stage, 'full_archive_verified': evidence == ARCHIVE,
               'startup_recovery': 'Missing auxiliary configuration links on the first attempt, zero model sends.'}
    store(release / 'summary.json', scrub(summary))
    store(release / 'per-question.json', scrub(runs))
    store(release / 'initial-graph.json', scrub(graph))
    table = []
    for label in MODELS:
        info = results[label]
        s = info['score']
        table.append(f"| {LABELS[label]} | {s['correct']}/60 | {s['correct']/60:.1%} | "
                     f"{s['main_calls']} | {s['tool_calls']} | {s['tool_failures']} | "
                     f"{info['seconds_to_last_prediction']/60:.1f} 分钟 |")
    qwen_n = len(pair['qwen_only_correct'])
    deepseek_n = len(pair['deepseek_only_correct'])
    if evidence == ARCHIVE:
        image_note = '逐题记录包含题干、完整选项、预测、对错、工具观察、原图及本轮生成图像路径。'
    else:
        image_note = '逐题记录包含题干、完整选项、预测、对错、工具观察和 Open-i 原图链接。完整调用记录和工具图像保存在 AutoDL，正分段同步到 H 盘。'
    body = f'''# R55 M14 GSEM · AutoDL OpenI-60

| 主回答模型 | 答对 | 准确率 | 主模型调用 | 工具调用 | 工具失败 | 到最后一题落盘 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

逐题配对中，两组共同答对 {len(pair['both_correct'])} 题、共同答错 {len(pair['both_wrong'])} 题。Qwen 独对 {qwen_n} 题，DeepSeek 独对 {deepseek_n} 题。两组各有 60 条预测、60 条检索和 60 条反馈更新记录，均正常退出。

两组用相同的 OpenI 60 题、原图、题序、11 个工具、18 个经验节点、41 条初始边和逐题更新规则。标注在当题预测落盘后释放。RTX 6000D 上的工具由现有常驻进程执行，胸片专家是 StanfordAIMI/CheXagent-8b，版本为 `{stage['chexagent_revision']}`。Qwen3.6-Flash 和 DeepSeek V4.1 Flash 通过同一 Token Plan 调用，后者固定到 `deepseek-v4.1-flash-1017`。模型辅助角色沿用实验室配置。初次启动缺少辅助配置链接，在付费请求前退出，补齐后重启。

工具由模型按提示自行选择。DeepSeek 60 题均在首轮给出可评分答案，未发出 `calls`。工具参与度是两组观察到的行为差异。此处的配对分差反映这批题上的整套运行表现。

请求用量、模型返回标识、工具路线和计时见摘要。记录的 token 统计可与 Token Plan 扣费对账。 [摘要](summary.json)

{image_note} [逐题记录](per-question.json) · [初始图](initial-graph.json) · [运行源码](source)

题目来自 Stanford AIMI CheXBench。胸片来自 Indiana University 医院网络，由美国国立卫生研究院国家医学图书馆（NLM, NIH, Bethesda, MD, USA）发布。 [CheXBench 数据卡](https://huggingface.co/datasets/StanfordAIMI/chexbench) · [Open-i 数据来源](https://openi-vip.nlm.nih.gov/faq) · [Demner-Fushman 等](https://pubmed.ncbi.nlm.nih.gov/26133894/)
'''
    (release / 'README.md').write_text(body, encoding='utf-8')
    return summary


def git(*args, env=None, data=None):
    return subprocess.check_output(['git', *args], cwd=REPO, env=env, input=data)


def publish(release):
    if git('remote', 'get-url', '--push', 'origin').decode().strip() != REMOTE:
        raise ValueError('Unexpected experiment report destination')
    existing = git('ls-remote', '--heads', 'origin', BRANCH).decode().split()
    if existing:
        receipt = ARCHIVE / 'publication.report.json'
        if not receipt.is_file() or json.loads(receipt.read_bytes())['commit'] != existing[0]:
            raise ValueError('The existing report branch has no matching local publication receipt')
        source = BRANCH
    else:
        source = 'refs/heads/main'
    ref = 'refs/codex/r55-gsem-autodl-publication-base'
    git('fetch', '--no-tags', 'origin', '+' + source + ':' + ref)
    base = git('rev-parse', ref).decode().strip()
    env = dict(os.environ, GIT_INDEX_FILE=str(release.parent / 'git-index'))
    git('read-tree', base, env=env)
    entries = []
    for p in sorted(release.rglob('*')):
        if not p.is_file():
            continue
        if p.suffix in ('.py', '.json', '.md') and TOKEN.search(p.read_text(encoding='utf-8')):
            raise ValueError(f'Token-like text in publishing file: {p.name}')
        oid = git('hash-object', '-w', '--no-filters', str(p)).decode().strip()
        entries.append(f'100644 {oid}\t{REPORT}/{p.relative_to(release).as_posix()}\0')
    git('update-index', '--add', '-z', '--index-info', env=env, data=''.join(entries).encode())
    tree = git('write-tree', env=env).decode().strip()
    commit = git('commit-tree', tree, '-p', base, '-m', 'Publish AutoDL MedRAX R55 M14 OpenI-60 results').decode().strip()
    git('push', 'origin', commit + ':' + BRANCH)
    if git('ls-remote', '--heads', 'origin', BRANCH).decode().split() != [commit, BRANCH]:
        raise ValueError('Remote report commit was not confirmed')
    return {'commit': commit, 'url': f'https://github.com/cw462/MedRAX-reproduction/blob/{commit}/{REPORT}/README.md'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-only', action='store_true')
    compact = parser.parse_args().report_only
    state = execute('status')
    if not all(arm['exit'] == 0 and arm['saved'] == arm['ingested'] == 60 for arm in state['arms'].values()):
        raise ValueError('Both AutoDL M14 scores are required before publication')
    if compact:
        evidence = archive_report(state)
    else:
        archive(state)
        evidence = ARCHIVE
    with TemporaryDirectory(prefix='m14-autodl-publish-') as scratch:
        release = Path(scratch) / 'report'
        release.mkdir()
        summary = render(state, release, evidence)
        if not compact:
            store(ARCHIVE / 'archive.completed.json', summary)
        published = publish(release)
    store(ARCHIVE / ('publication.report.json' if compact else 'publication.completed.json'), published)
    print(json.dumps({'archive': str(evidence), **published, 'scores': {
        label: arm['score']['correct'] for label, arm in summary['arms'].items()}}))
