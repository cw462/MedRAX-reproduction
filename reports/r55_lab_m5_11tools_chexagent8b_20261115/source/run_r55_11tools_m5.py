"""Run R55 M5 with CerebraFusionMemory and all 11 tools."""

import argparse
import json
import os
from pathlib import Path
from shutil import disk_usage
import sys
import time

import r55_memevolve_driver003 as bridge
from run_r55_full848_dataset import ARMS, COUNTS


def read_json(path):
    return json.loads(path.read_bytes())


class CheckpointMemory(bridge.Memory):
    """Reopen a saved graph after a rejected retrieval with no saved prediction."""

    def __init__(self, runtime, out, key, inputs, fixture=None):
        ids = [row['question_id'] for row in inputs]
        episodes = out/'episodes'
        predictions = out.parent/'predictions'/ARMS['M5']
        saved = {path.stem for path in predictions.glob('*.json')}
        self.prefix = set(ids[:len(saved)])
        for name in ('retrieval.json', 'ingest.json'):
            if {path.parent.name for path in episodes.glob('*/'+name)} != self.prefix:
                raise ValueError('M5 checkpoint has incomplete saved memory for a prediction')
        if saved != self.prefix:
            raise ValueError('M5 checkpoint predictions are not a frozen input prefix')

        ledger = out/'model_calls'
        calls = {path.parent for path in ledger.glob('*/*/*/result.json')}
        if (calls != {path.parent for path in ledger.glob('*/*/*/started.json')}
                or sorted(int(path.name) for path in calls) != list(range(1, len(calls)+1))):
            raise ValueError('M5 checkpoint has an unclosed or out-of-order memory call')

        retry = None
        if len(saved) < len(ids):
            row = inputs[len(saved)]
            qid = row['question_id']
            folder = episodes/qid
            starts = list(folder.glob('retrieval.started*.json'))
            extra = {p.parent.name for p in episodes.glob('*/retrieval.started*.json')} - self.prefix
            if extra - {qid} or any(not (episodes/q/'retrieval.started.json').is_file() for q in self.prefix):
                raise ValueError('M5 checkpoint has retrieval records outside the saved prefix')
            if starts:
                receipt = max(calls, key=lambda path: int(path.name), default=None)
                if (receipt is None or receipt.parent != ledger/qid/'retrieve'
                        or (receipt/'response.raw').exists()
                        or (out.parent/'services/calls/R49-AGENT'/qid).exists()
                        or any(read_json(p)['query'] != bridge.question(row) for p in starts)):
                    raise ValueError('M5 checkpoint has unresolved retrieval evidence')
                result = read_json(receipt/'result.json')
                if result['response_received'] is not False or result['error'] != 'HTTPError':
                    raise ValueError('M5 recovery requires a terminal rejected retrieval')
                retry = qid

        graph_path = out.parent/'storage/cerebra_fusion_memory/cf_database.json'
        graph = read_json(graph_path) if graph_path.is_file() else None
        ingests = [read_json(episodes/q/'ingest.json') for q in ids[:len(saved)]]
        if ingests and (graph is None or not ingests[-1]['native_description'].startswith('Ingested ')):
            raise ValueError('M5 persisted graph does not cover the last completed ingest')
        super().__init__('M5', runtime, out, key, fixture)
        provider = self.provider
        if provider.enable_tool_memory or provider.active_usage_tracking:
            raise ValueError('M5 checkpoint tool memory or retrieval state changed')
        if graph is not None and ([vars(node) for node in provider.nodes.values()] != graph['nodes']
                                  or [edge.to_dict() for edge in provider.edges] != graph['edges']):
            raise ValueError('M5 native graph did not restore exactly')
        if not saved and len(provider.nodes) != 7:
            raise ValueError('M5 seed graph changed')
        ingested = sum(item['native_description'].startswith('Ingested ') for item in ingests)
        provider.task_counter = ingested % provider.consolidation_interval
        self.model.calls = len(calls)
        from r55_memory_token_plan import enabled

        self.model.use_token_plan = enabled(Path(__file__).resolve().parent)
        self.retry_question = retry

    def retrieve(self, row):
        if row['question_id'] == self.retry_question:
            marker = self.out/'episodes'/self.retry_question/'retrieval.started.json'
            if marker.is_file():
                marker.rename(marker.with_name(f'retrieval.started.before-{time.time_ns()}.json'))
            self.retry_question = None
        return super().retrieve(row)

    def ingest(self, row, trace, feedback):
        qid = row['question_id']
        if qid not in self.prefix:
            return super().ingest(row, trace, feedback)
        saved = read_json(self.out/'episodes'/qid/'ingest.json')
        if (saved['prediction_saved_at'] != trace['prediction']['prediction_saved_at']
                or saved['feedback_released_at'] != feedback['released_at']):
            raise ValueError('M5 saved prediction or feedback no longer matches its ingest')


def run_dataset(code, out, data, references, runtime):
    sys.path.insert(0, str(code/'experiments'))
    import run_online_skill_r54 as engine
    from cxr_online_primitives_r49 import rows
    from online_memory_r49 import ReferenceVault, read, save_once
    from run_cxr_vqa_toolsets import exclusive_lock
    from skill_services_r55 import Services

    manifest = read(out/'manifest.json')
    inputs, order = manifest['inputs'], manifest['order']
    ids = [row['question_id'] for row in inputs]
    tools = manifest['runtime']['arms']['M']['tools']
    assert len(ids) == len(set(ids)) == COUNTS[manifest['dataset']]
    assert rows(data/'inputs.jsonl') == inputs
    assert [row['question_id'] for row in order] == ids
    assert set(manifest['reference_files']) == set(ids) and len(tools) == 11
    assert manifest['arm'] == ARMS['M5'] and not manifest['skill_enabled']
    assert manifest['memory_provider'] == bridge.PROVIDERS['M5']
    assert manifest['memory_source'] == bridge.SOURCE and not manifest['cerebra_generated_tools']
    gpu = os.environ['CUDA_VISIBLE_DEVICES']
    assert gpu in ('0','1') and os.environ['R55_MEMEVOLVE_GPU'] == gpu
    engine.ARM = manifest['arm']
    main_key, memory_key = [sys.stdin.readline().strip() for _ in range(2)]
    assert main_key and memory_key
    service = Services(manifest['config'], manifest['protocol'], manifest['runtime'],
                       out/'services', main_key, manifest['embedding_model'],
                       manifest['embedding_base_url'])
    vault = ReferenceVault(references, manifest['reference_files'])
    complete = out/'complete.json'
    final_memory = out/'memory.completed.json'
    if complete.is_file() and final_memory.is_file():
        return read(final_memory)

    class DiskGuardedMemory(CheckpointMemory):
        def retrieve(self, row):
            if disk_usage(out).free < 256 * 1024**2:
                raise RuntimeError('r55_full848_m5_disk_below_256_mib_before_question')
            return super().retrieve(row)

    bridge.load_runtime(runtime, out)
    with exclusive_lock(out/'.online.lock'):
        memory_root = out/'external_memory'
        memory = DiskGuardedMemory(runtime, memory_root, memory_key, inputs)
        engine.run_stream(inputs, order, data, out, service, vault, tools,
                          evolver=engine.disabled_evolve, external_memory=memory)
        done = read(complete)
        assert done['arm'] == ARMS['M5'] and done['questions'] == len(ids)
        for receipt in ('retrieval.json','ingest.json'):
            assert {p.parent.name for p in (memory_root/'episodes').glob('*/'+receipt)} == set(ids)
        result = {'dataset':manifest['dataset'], 'questions':len(ids),
                  'memory_model_calls':memory.model.calls, 'provider':bridge.PROVIDERS['M5']}
        save_once(final_memory, result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('code','out','data','references','runtime'):
        parser.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(run_dataset(**vars(parser.parse_args()))))
