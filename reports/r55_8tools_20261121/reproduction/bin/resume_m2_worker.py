"""Complete an interrupted native ExpeL ingest from its saved call evidence."""

import json
from pathlib import Path
import runpy
import sys

import r55_autodl_memory_recovery_official as recovery
from r55_deepseek_official import MODEL, valid_response
from r55_memevolve_driver_official import Memory, question


ROOT = Path(__file__).resolve().parents[1]


def cohort(model, dataset):
    if model not in ('deepseek', 'flash', 'plus') or dataset not in ('slake', 'vqarad', 'chexbench'):
        raise ValueError('Expected a planned R55 model and dataset')
    return ROOT / model / 'generation/M2' / dataset


def response(call):
    result = recovery.read(call / 'result.json')
    raw = recovery.read(call / 'response.raw')
    choice = raw['choices'][0]
    content = choice['message']['content']
    if (result.get('response_received') is not True or result.get('error')
            or not valid_response(raw) or choice['finish_reason'] != 'stop'
            or not isinstance(content, str) or not content.strip()):
        raise ValueError('The archived ExpeL response is incomplete')
    return content


def insight_lines(content):
    lines = []
    for line in content.splitlines():
        line = line.strip().lstrip('•-*123456789. ')
        for prefix in ('Do:', 'Avoid:', 'Insight:', 'Tip:', 'Note:'):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        if len(line) > 10:
            lines.append(line)
    return lines[:4]


def checkpoint(work):
    memory = work / 'external_memory'
    episodes = memory / 'episodes'
    ledger = memory / 'model_calls'
    manifest = recovery.read(work / 'manifest.json')
    ids = [row['question_id'] for row in manifest['inputs']]
    predictions = {path.stem for path in (work / 'predictions/R55-M2').glob('*.json')}
    ingests = {path.parent.name for path in episodes.glob('*/ingest.json')}
    count = len(predictions)
    if (manifest['memory_provider'] != 'expel' or not count or predictions != set(ids[:count])
            or ingests != set(ids[:count-1])):
        raise ValueError('The predictions and committed ExpeL writes do not match the frozen prefix')
    row = manifest['inputs'][count-1]
    qid = row['question_id']
    marker = episodes / qid / 'ingest.started.json'
    trajectory = recovery.read(marker)['trajectory']
    feedback = recovery.read(work / 'feedback' / f'{qid}.json')
    if (feedback['saved_prediction'] != recovery.read(work / 'predictions/R55-M2' / f'{qid}.json')
            or trajectory['metadata']['task_id'] != qid or trajectory['query'] != question(row)
            or not trajectory['metadata']['is_correct']):
        raise ValueError('The unfinished ingest does not match the saved successful prediction')

    closed = {path.parent for path in ledger.glob('*/*/*/result.json')}
    starts = {path.parent for path in ledger.glob('*/*/*/started.json')}
    ordered = sorted(closed, key=lambda path: int(path.name))
    calls = sorted((ledger / qid / 'ingest').glob('*'), key=lambda path: int(path.name))
    if (closed != starts or [int(path.name) for path in ordered] != list(range(1, len(ordered)+1))
            or len(calls) not in (1, 2) or ordered[-len(calls):] != calls):
        raise ValueError('Expected the closed ExpeL ledger ending at the current ingest calls')
    last = calls[-1]
    cached = calls[0] if len(calls) == 2 else None
    saved_response = response(cached) if cached else None
    failed = recovery.read(last / 'result.json')
    requests = [recovery.read(call / 'request.json') for call in calls]
    if (failed.get('error') != 'TimeoutError' or failed.get('response_received') is not False
            or (last / 'response.raw').exists() or any(request['model'] != MODEL for request in requests)):
        raise ValueError('The final ExpeL transmission must have a timeout receipt with no response')

    native = work / 'storage/expel'
    native_insights = recovery.read(native / 'insights.json')
    native_trajectories = recovery.read(native / 'success_trajectories.json')
    expected_insights, expected_trajectories = [], []
    for item in ids[:count]:
        saved = recovery.read(episodes / item / 'ingest.started.json')['trajectory']
        success = saved['metadata']['is_correct']
        if item == qid:
            extracted = insight_lines(saved_response) if saved_response is not None else []
            summary = ''
        else:
            item_calls = sorted((ledger / item / 'ingest').glob('*'), key=lambda path: int(path.name))
            successful = [call for call in item_calls if recovery.read(call / 'result.json')['response_received'] is True]
            if len(successful) != 1 + int(success):
                raise ValueError('A committed ExpeL case has unexpected successful call receipts')
            extracted = insight_lines(response(successful[0]))
            summary = response(successful[1]).strip() if success else ''
        expected_insights.extend((line, 'success' if success else 'failure') for line in extracted)
        if success:
            expected_trajectories.append((saved['query'], saved['result'], saved['metadata'], summary))
    if [(entry['text'], entry['type']) for entry in native_insights] != expected_insights:
        raise ValueError('The persisted insights differ from the committed calls and cached response')
    if [(entry['query'], entry['result'], entry['metadata'], entry['trajectory_text'])
            for entry in native_trajectories] != expected_trajectories:
        raise ValueError('The persisted trajectories do not end with the isolated empty fallback')
    return {
        'qid': qid, 'marker': marker, 'requests': requests, 'saved_response': saved_response,
        'trajectory': trajectory, 'fallback': native_trajectories[-1], 'saved_predictions': count,
        'cached_insight_call': int(cached.name) if cached else None, 'failed_call': int(last.name),
    }


def run(work):
    proof = checkpoint(work)
    qid, marker, requests = proof['qid'], proof['marker'], proof['requests']
    saved_response, trajectory, fallback = proof['saved_response'], proof['trajectory'], proof['fallback']
    store = work / 'storage/expel/success_trajectories.json'
    archive = work / 'external_memory/recovery' / qid / f"expel-ingest-{proof['failed_call']}"
    archive.mkdir(parents=True)
    recovery.replace_json(archive / 'native_fallback.json', fallback)
    marker.rename(archive / marker.name)

    class ResumedMemory(Memory):
        def ingest(self, row, trace, feedback):
            if row['question_id'] != qid:
                return super().ingest(row, trace, feedback)

            provider = self.provider
            model = self.model
            fixture = model.fixture
            append_insights = provider._append_insights
            append_trajectory = provider._append_success_trajectory
            replayed = 0

            def require(condition, detail):
                if not condition:
                    model.failure = 'expel_checkpoint_changed'
                    raise ValueError(detail)

            def replay(messages):
                nonlocal replayed
                require(replayed < len(requests) and messages == requests[replayed]['messages'],
                        'The resumed ExpeL request differs from its original')
                replayed += 1
                if saved_response is not None and replayed == 1:
                    return saved_response
                model.fixture = fixture
                return model(messages)

            def preserve_insights(insights, is_correct):
                require(replayed == 1 and is_correct and insights == insight_lines(saved_response),
                        'The already persisted ExpeL insights changed')

            def complete_trajectory(value):
                require(value.query == trajectory['query'] and value.result == trajectory['result']
                        and value.metadata == trajectory['metadata'], 'The ExpeL fallback identity changed')
                summary = provider._refine_successful_trajectory_with_llm(value)
                self.checked()
                records = recovery.read(store)
                require(replayed == len(requests) and bool(summary.strip()) and records[-1] == fallback,
                        'The pending ExpeL trajectory could not be completed')
                records[-1] = dict(fallback, trajectory_text=summary)
                recovery.replace_json(store, records)
                provider.success_trajectories = records

            model.fixture = replay
            if saved_response is not None:
                provider._append_insights = preserve_insights
            provider._append_success_trajectory = complete_trajectory
            try:
                outcome = super().ingest(row, trace, feedback)
                receipt = recovery.read(marker.with_name('ingest.json'))
                require(replayed == len(requests) and receipt['accepted'] is True,
                        'The resumed ExpeL ingest did not commit')
                return outcome
            finally:
                model.fixture = fixture
                provider._append_insights = append_insights
                provider._append_success_trajectory = append_trajectory

    recovery.RecoveryMemory = ResumedMemory
    runpy.run_path(str(ROOT / 'bin/run_qwen8_memory.py'), run_name='__main__')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--check']:
        model, dataset = sys.argv[2:] or ('deepseek', 'slake')
        proof = checkpoint(cohort(model, dataset))
        count = proof['saved_predictions']
        print(json.dumps({'pending_case': proof['qid'], 'saved_predictions': count,
                          'committed_ingests': count-1, 'cached_insight_call': proof['cached_insight_call'],
                          'failed_call': proof['failed_call']}))
    else:
        _, model_root, arm, _, dataset = sys.argv[1:]
        if arm != 'M2':
            raise ValueError('Expected the R55 M2 native generation arguments')
        run(cohort(Path(model_root).name, dataset))
