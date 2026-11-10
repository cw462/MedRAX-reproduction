"""Enable all three existing CXRAgent backends without launching inference."""
import argparse
import copy
import json
from pathlib import Path

NEW = ('medgemma', 'llava_rad', 'medvlm_r1')
PATHS = ('medgemma_model', 'medvlm_model', 'llavarad_source',
         'llavarad_model', 'vicuna_model', 'biomedbert_config')

def enable(runtime, donor):
    result = copy.deepcopy(runtime)
    # R49 reconstructs R49-AGENT from M at startup: change M as well.
    names = ['medgemma', 'llava_rad', 'chest_xray_expert', 'llava_med_qa', 'xray_phrase_grounding', 'medvlm_r1']
    for name in NEW:
        record = copy.deepcopy(donor['tools'][name])
        if record.get('backend') != name:
            raise ValueError('Unexpected backend: ' + name)
        record['deployment_status'] = 'configured_current_load_not_checked'
        result['tools'][name] = record
    for key in PATHS:
        result.setdefault('backend_config', {})[key] = donor['backend_config'][key]
    for arm in ('M', 'R49-AGENT'):
        value = copy.deepcopy(result['arms'].get(arm, result['arms']['M']))
        value['tools'] = names.copy()
        value['label'] = 'R50-CXRAgent6'
        result['arms'][arm] = value
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True, help='Existing PRIVATE R49 config')
    p.add_argument('--donor-runtime', type=Path, required=True, help='PRIVATE historical C ready runtime')
    p.add_argument('--out-dir', type=Path, required=True, help='New config directory, never old run outputs')
    p.add_argument('--template-only', action='store_true', help='Allow redacted paths; not runnable')
    a = p.parse_args()
    cfg = json.loads(a.config.read_text(encoding='utf-8'))
    # Preserve the same working-directory semantics as the existing R49 runner.
    runtime_path = Path(cfg['runtime']).resolve()
    protocol_path = Path(cfg['protocol']).resolve()
    runtime = json.loads(runtime_path.read_text(encoding='utf-8'))
    donor = json.loads(a.donor_runtime.read_text(encoding='utf-8'))
    updated = enable(runtime, donor)
    required = [updated['backend_config'][k] for k in PATHS]
    required += [updated['tools'][n]['python'] for n in NEW]
    if not a.template_only and any(not isinstance(v, str) or not v.strip() or
            '[REDACTED]' in v or '<' in v for v in required):
        raise ValueError('Use private deployed runtime with real model/interpreter paths, not GitHub redactions.')
    out = a.out_dir.resolve()
    if out.exists():
        raise FileExistsError('Use a new directory; existing outputs are never overwritten.')
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    out.mkdir(parents=True)
    cfg['runtime'] = str(out / 'runtime.json')
    cfg['protocol'] = str(protocol_path)
    for filename, value in [('runtime.json', updated), ('config.json', cfg)]:
        (out / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'tools': updated['arms']['M']['tools'], 'count': len(updated['arms']['M']['tools']),
        'config': str(out/'config.json'), 'template_only': a.template_only,
        'model_load_checked': False, 'inference_started': False}, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
