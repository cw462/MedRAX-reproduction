"""Export authorized benchmark inputs and cached evidence for V11 case review.

This is an offline publication transform. It performs no inference, grading,
network access, credential lookup or ledger access. The private source cache
contains image files and a manifest of already completed comparison packets.
Only explicitly selected result fields enter the public package; image bytes
are copied unchanged. Benchmark media are third-party data, not repository code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote

from PIL import Image

DATASET = 'wanglab/chest-agent-bench'
REVISION = '921e60440927f9893228d843c0206b755744252a'
DATASET_URL = f'https://huggingface.co/datasets/{DATASET}/tree/{REVISION}'
README_URL = f'https://huggingface.co/datasets/{DATASET}/raw/{REVISION}/README.md'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def clean(value, image_mapping):
    """Replace local paths and reject accidental secret/base64 payloads."""
    if isinstance(value, dict):
        return {key: clean(item, image_mapping) for key, item in value.items()
                if key.lower() not in {'api_key', 'password', 'authorization', 'access_token',
                                       'credential', 'credentials', 'secret', 'k_block', 'e_block'}}
    if isinstance(value, list):
        return [clean(item, image_mapping) for item in value]
    if not isinstance(value, str):
        return value
    if re.search(r'data:image/[^;]+;base64,', value, re.I):
        raise ValueError('base64_image_payload_not_allowed_in_public_text')
    for private, public in sorted(image_mapping.items(), key=lambda item: -len(item[0])):
        value = value.replace(private, public)
    value = re.sub(r'(?i)(?:(?<![A-Za-z0-9])[a-z]:[\\/]|/(?:home|tmp|mnt|Users)/)[^\s\"\'<>\]\},]+',
                   '[private_path_omitted]', value)
    if re.search(r'(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{25,})\b', value):
        raise ValueError('credential_like_value_not_allowed')
    return value


def image_view(image, mapping):
    allowed = ('image_id', 'role', 'size', 'parent_image_id', 'pixel_box',
               'source_size', 'orientation', 'timepoint')
    result = {k: image[k] for k in allowed if k in image}
    result['path'] = mapping[image['path']]
    return result


def stage_view(row):
    keys = ('stage', 'initial', 'candidate', 'final', 's1_final', 'route', 'selector',
            'fallback', 'followup_question', 'action', 'new_observation', 'blind_observation',
            'timing')
    result = {k: row[k] for k in keys if k in row}
    result['selector_error_type'] = str(row['selector_error']).split(':', 1)[0] if row.get('selector_error') else None
    return result


def markdown(case):
    qid = case['question_id']
    lines = [f'# Benchmark case {qid}', '',
             '[Case index](README.md) · [Machine-readable case](%s.json) · [Scored outcomes](../per-question-outcomes.json)' % quote(qid), '',
             f"Source: [Eurorad case {case['source']['case_id']}]({case['source']['case_url']}); "
             f"[ChestAgentBench pinned revision]({DATASET_URL}).", '',
             'These are the benchmark inputs used in the frozen experiment. Model and tool observations '
             'below are recorded outputs, not independently validated clinical findings.', '',
             '## Full question and options', '', '```text',
             '\n'.join(line.rstrip() for line in case['question'].split('\n')), '```', '',
             '## Original benchmark images', '']
    for im in case['original_images']:
        lines += [f"### {im['image_id']} — {im['source_filename']}", '',
                  f"![Original {im['image_id']}](../{quote(im['path'])})", '']
    lines += ['## Recorded answers', '', '| Stage | Answer | Execution route/status |', '|---|---|---|',
              f"| P0 | {case['p0'].get('answer') or 'missing'} | {case['p0']['status']} |",
              f"| V10 VKE candidate | {case['v10_vke'].get('candidate') or 'missing'} | candidate before gate |",
              f"| V10 VKE final | {case['v10_vke'].get('final') or 'missing'} | {case['v10_vke'].get('gate',{}).get('decision','')} |"]
    for name, value in case['v11'].items():
        lines.append(f"| {name} | {value.get('final') or 'missing'} | {value.get('route','')} |")
    if case.get('reference_answer'):
        lines += ['', f"Reference answer (post-generation scoring only): **{case['reference_answer']}**."]
    lines += ['', '## V10 VKE candidate and gate record', '', '```json',
              json.dumps(case['v10_vke'], ensure_ascii=False, indent=2), '```', '']
    packet = case.get('cached_comparison')
    if packet:
        lines += ['## Cached anonymous comparison', '',
                  'The X/Y mapping and observation provenance are exposed here for retrospective review. '
                  'They were kept separate from the selector-facing anonymous input.', '', '```json',
                  json.dumps({k: packet[k] for k in ('answer_mapping','choices','evidence_mapping','cached_image_adjustments')},
                             ensure_ascii=False, indent=2), '```', '', '### Additional cached pixels', '']
        extras = [im for im in packet['images'] if im['role'] != 'original']
        if not extras: lines += ['No additional cached image was used for this comparison.', '']
        for im in extras:
            meta = {k:v for k,v in im.items() if k!='path'}
            lines += [f"**{im['image_id']}**", '', f"![{im['image_id']}](../{quote(im['path'])})", '',
                      '```json',json.dumps(meta,ensure_ascii=False,indent=2),'```','']
        lines += ['### Cached tool observations', '',
                  'Tool request and return text is preserved; private filesystem paths are replaced by '
                  'image links or an omission marker. Tool conclusions remain fallible.', '']
        for observation in packet['tool_observations']:
            lines += [f"#### {observation['observation_id']} — {observation.get('tool','')}", '',
                      '```json',json.dumps(observation,ensure_ascii=False,indent=2),'```','']
    else:
        lines += ['## Detailed comparison evidence', '',
                  'This case did not route to the 21-case anonymous disagreement selector. '
                  'Its original input and recorded answers are included; no selector packet was generated.', '']
    followup = case.get('s2_followup')
    if followup:
        lines += ['## S2 targeted follow-up action and reader observation', '', '```json',
                  json.dumps(followup,ensure_ascii=False,indent=2),'```','']
        for im in followup.get('action',{}).get('images',[]):
            if im.get('image_id') == 'followup_image_1':
                lines += [f"![S2 follow-up crop](../{quote(im['path'])})", '']
    lines += ['## V11 selector and reader records', '',
              'A recorded choice can coexist with an empty observation list. That record alone does not '
              'establish a supported visual comparison. See the [decision audit](../decision-audit.json) '
              'and [decision-pattern analysis](../decision-pattern-analysis.md) for this limitation.', '', '```json',
              json.dumps(case['v11'],ensure_ascii=False,indent=2),'```','',
              '[Data provenance and limits](../data-provenance.md)', '']
    return '\n'.join(lines)


def export(args):
    cache, out = args.cache.resolve(), args.out.resolve()
    manifest = read_json(cache/'manifest.json')
    selection = read_json(args.source/'selection.json')
    rows = selection['rows']
    if len(rows) != 60 or len({r['question_id'] for r in rows}) != 60:
        raise ValueError('expected_frozen_sixty')
    mapping = manifest['image_mapping']
    p0 = {r['question_id']:r for r in read_rows(args.source/'p0_results.jsonl')}
    vke = {r['question_id']:r for r in read_rows(args.source/'candidate_results.jsonl') if r['group']=='VKE'}
    stages = {name:{r['question_id']:r for r in read_rows(path/'results.jsonl')}
              for name,path in [('S1',args.s1),('S2',args.s2),('S3',args.s3)]}
    references = read_json(args.references) if args.references else {}
    if isinstance(references,dict) and 'records' in references:
        references={record['question_id']:record['reference_answer'] for record in references['records']
                    if record.get('reference_answer')}
    if args.references and any(row['question_id'] not in references for row in rows):
        raise ValueError('reference_export_incomplete')
    out.mkdir(parents=True,exist_ok=True)
    image_manifest = []
    prior_images = ({entry['path']:entry for entry in read_json(out/'cases.json')['image_manifest']}
                    if args.reuse_published_images else {})
    for relative in sorted(set(mapping.values())):
        if not relative.startswith('images/') or '..' in Path(relative).parts:
            raise ValueError('unsafe_public_image_path')
        source, dest = cache/relative, out/relative
        if args.reuse_published_images:
            entry=prior_images[relative]
            if not dest.is_file() or dest.stat().st_size!=entry['bytes']:
                raise ValueError('published_image_missing_or_size_changed')
            image_manifest.append(entry)
        else:
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
            with Image.open(source) as image: size=list(image.size)
            image_manifest.append({'path':relative,'bytes':source.stat().st_size,'size':size,
                                   'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                                   'byte_preserving_copy':True})
    by_path = {im['path']:im for im in image_manifest}
    cases = []
    for index,row in enumerate(rows,1):
        qid=row['question_id']; case_id=qid.split('_',1)[0]
        originals=[]
        for n,source_name in enumerate(row['images'],1):
            relative='images/originals/'+source_name
            originals.append({'image_id':f'image:{n}','source_filename':source_name,
                              **by_path[relative]})
        branch=vke[qid]
        branch_fields=('candidate','final','changed_attributes','candidate_payload','gate','fallback','k_ids','e_ids')
        candidate={k:branch[k] for k in branch_fields if k in branch}
        for error in ('candidate_error','gate_error'):
            candidate[error+'_type']=str(branch[error]).split(':',1)[0] if branch.get(error) else None
        case={'index':index,'question_id':qid,'question':row['question'],
              'official_group':row.get('official_group'),'source':{'dataset':DATASET,'revision':REVISION,
              'case_id':case_id,'case_url':f'https://www.eurorad.org/case/{case_id}'},
              'original_images':originals,'p0':{'answer':p0[qid].get('initial'),
              'status':p0[qid]['status'],'error_type':p0[qid].get('report',{}).get('error_type')},
              'v10_vke':candidate,'v11':{name:stage_view(values[qid]) for name,values in stages.items()},
              'detailed_disagreement':qid in manifest['comparisons']}
        if qid in references:case['reference_answer']=references[qid]
        if qid in manifest['comparisons']:
            packet=manifest['comparisons'][qid]
            case['cached_comparison']={'answer_mapping':packet['private_mapping'],
                 'choices':packet['comparison_text']['choices'],'refs':packet['refs'],
                 'images':[image_view(im,mapping) for im in packet['images']],
                 'tool_observations':packet['observations'],'evidence_mapping':packet['evidence_mapping'],
                 'cached_image_adjustments':packet['comparison_text'].get('cached_image_adjustments',[])}
        if qid in manifest['followups']:
            followup=manifest['followups'][qid]
            action=followup.get('action',{})
            case['s2_followup']={'action_plan':followup.get('action_plan'),
                  'action':{k:v for k,v in action.items() if k!='images'},'observation':followup.get('observation')}
            case['s2_followup']['action']['images']=[image_view(im,mapping) for im in action.get('images',[])]
        case=clean(case,mapping)
        write_json(out/'cases'/f'{qid}.json',case)
        (out/'cases'/f'{qid}.md').write_text(markdown(case),encoding='utf-8')
        cases.append(case)
    payload={'schema_version':1,'dataset':DATASET,'revision':REVISION,'dataset_url':DATASET_URL,
             'reference_visibility':'post_generation_publication_only','case_count':len(cases),
             'detailed_disagreement_count':sum(c['detailed_disagreement'] for c in cases),
             'original_image_count':sum('/originals/' in im['path'] for im in image_manifest),
             'image_count':len(image_manifest),'image_bytes':sum(im['bytes'] for im in image_manifest),
             'image_manifest':image_manifest,'cases':cases}
    write_json(out/'cases.json',payload)
    index=['# Fixed 60-case review index','','[Report index](../README.md) · [All cases as JSON](../cases.json) · [Data provenance](../data-provenance.md)',
           '', '| # | Question | Detailed disagreement evidence | Original images |', '|---:|---|---|---:|']
    for c in cases:index.append(f"| {c['index']} | [{c['question_id']}]({quote(c['question_id'])}.md) | {'yes' if c['detailed_disagreement'] else 'no'} | {len(c['original_images'])} |")
    (out/'cases'/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    print(json.dumps({k:payload[k] for k in ['case_count','detailed_disagreement_count','original_image_count','image_count','image_bytes']}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('local_assets/v11_public_sources'))
    p.add_argument('--source',type=Path,default=Path('runs/v10_accuracy60'))
    p.add_argument('--s1',type=Path,default=Path('runs/v11_selector60'))
    p.add_argument('--s2',type=Path,default=Path('runs/v11_followup60'))
    p.add_argument('--s3',type=Path,default=Path('runs/v11_blindread60'))
    p.add_argument('--references',type=Path)
    p.add_argument('--reuse-published-images',action='store_true',
                   help='Update case text using the existing immutable image manifest without copying or hashing images again.')
    p.add_argument('--out',type=Path,default=Path('reports/v11'))
    export(p.parse_args())


if __name__=='__main__':main()
