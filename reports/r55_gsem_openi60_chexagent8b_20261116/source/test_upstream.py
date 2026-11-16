"""Reproduce the live-neighbor score change on the released GSEM graph without API calls."""

from collections import defaultdict
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import subprocess
import sys
from types import ModuleType


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release(root):
    def prohibit_network(*args, **kwargs):
        raise AssertionError('The GSEM regression test may not call an API')

    local_agent = ModuleType('agent')
    local_agent.call_llm = prohibit_network
    sys.modules['agent'] = local_agent
    phase = root / 'src/phase3'
    ret = phase / 'retrieval'
    walker = load('retriver', ret / 'retriver.py')
    sys.modules['retriver'] = walker
    multi = load('retriver_multi_start_no_fill', ret / 'retriver_multi_start_no_fill.py')
    graph = load('upstream_graph_state', phase / 'ttl/graph_state.py')
    release = json.loads((ret / 'graph/experience_graph.json').read_bytes())
    nodes = {n['id']: n for n in release['nodes']}
    adjacency = defaultdict(list)
    initial = {}
    for edge in release['links']:
        a, b = edge['source'], edge['target']
        w = float(edge.get('weight', edge.get('W', 0.0)))
        initial[graph.GraphState.edge_key(a, b)] = w
        adjacency[a].append({'neighbor': b, 'W': w})
        adjacency[b].append({'neighbor': a, 'W': w})
    state = graph.GraphState(nodes, adjacency, {n: v['quality'] for n, v in nodes.items()}, {}, {}, {}, initial)
    src, dst = 'exp_0001', 'exp_0003'
    weight_before = state.get_current_weight(src, dst)
    static_before = dict(walker.get_top_neighbors(src, set(), top_k=len(adjacency[src])))[dst]
    with walker.use_graph_state(state):
        before = dict(walker.get_top_neighbors(src, set(), top_k=len(adjacency[src])))[dst]
        empty = type('EmptyFinder', (), {'find': lambda self, case: []})()
        assert multi.retrieve({'description': 'no match'}, empty) == []
    state.update_weights(1.0, [src, dst])
    weight_after = state.get_current_weight(src, dst)
    with walker.use_graph_state(state):
        after = dict(walker.get_top_neighbors(src, set(), top_k=len(adjacency[src])))[dst]
    assert round(weight_before, 4) == .5268 and round(weight_after, 4) == .6268
    assert math.isclose(before, static_before) and after > before
    assert math.isclose(after, (weight_after + state.node_qualities[dst]) / 2)
    assert static_before == dict(walker.get_top_neighbors(src, set(), top_k=len(adjacency[src])))[dst]
    subprocess.run([sys.executable, '-B', str(root / 'main_phase3.py'), '--help'], cwd=root,
                   check=True, capture_output=True, timeout=15)
    result = {'released_nodes': len(nodes), 'example_edge': [src, dst], 'weight_before': weight_before,
              'weight_after': weight_after, 'retrieval_score_before': before, 'retrieval_score_after': after,
              'zero_results_supported': True, 'api_calls': 0}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    test_release(Path(sys.argv[1]).resolve())
