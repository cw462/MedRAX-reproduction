"""Derive E3 eligibility from source figure captions, never question answers."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def caption_modality(caption):
    text = re.sub(r'\s+', ' ', caption.lower())
    # Temporal comparisons to a different CT do not change an explicitly
    # described chest radiograph's modality (no mixed-panel extrapolation).
    text = re.sub(r'(?:after the first|taken prior to the) chest?\s*ct(?: scan)?(?: in figure \d+)?', '', text)
    text = re.sub(r'taken prior to the ct scan in figure \d+', '', text)
    ct = bool(re.search(r'\bct\b|computed tomography|computerized tomography|ctpa|hrct', text))
    mr = bool(re.search(r'\bmri?\b|magnetic resonance|t[12][ -]weighted', text))
    xray = bool(re.search(r'x[ -]?ray|radiograph|\bcxr\b|roentgen|chest film', text))
    chest = bool(re.search(r'chest|thorac|thorax|lung|pulmon|pleur|mediast|hemithor|cardiac|cardiomeg|heart|costophren|rib[s ]|pneumothor|lower lobe|upper lobe|retrosternal', text))
    projection = bool(re.search(r'\bpa\b|\bap\b|postero[ -]?anterior|antero[ -]?posterior|frontal|lateral (?:view|projection|chest)', text))
    cxr = (xray and chest) or (projection and chest and bool(re.search(r'view|film|chest|projection', text)))
    # A multi-panel caption mentioning multiple modalities is insufficient to
    # assign this single source image to the chest-X-ray-only tool.
    if (ct or mr) and (xray or cxr):
        return 'unknown'
    if ct:
        return 'CT'
    if mr:
        return 'MRI'
    if re.search(r'ultrasound|sonograph|echograph', text):
        return 'US'
    if cxr:
        return 'CXR'
    return 'Xray' if xray else 'unknown'


def build(inputs, metadata):
    rows = [json.loads(x) for x in Path(inputs).read_text().splitlines() if x.strip()]
    # Only the figures/number/caption fields of the matching source cases are
    # projected; clinical narratives, diagnosis and reference answers are unused.
    source = json.loads(Path(metadata).read_text())
    cases = source if isinstance(source, dict) else {str(c['case_id']): c for c in source}
    wanted = sorted({image for r in rows for image in r['images']})
    captions = {}
    for cid in {str(r['case_id']) for r in rows}:
        case = cases.get(cid, {})
        for fig in case.get('figures', []):
            for sub in fig.get('subfigures', []):
                number = re.sub(r'\s+', '_', sub.get('number', '').strip().lower())
                filename = f'figures/{cid}/{number}.jpg'
                if filename in wanted:
                    caption = sub.get('caption') or ''
                    if filename in captions and captions[filename] != caption:
                        raise ValueError('conflicting_source_captions:'+filename)
                    captions[filename] = caption
    images = []
    for filename in wanted:
        caption = captions.get(filename, '')
        cid = filename.split('/')[1]
        images.append({'source_filename': filename, 'modality': caption_modality(caption),
            'provenance': {'kind': 'caption', 'source': f'https://www.eurorad.org/case/{cid}',
                           'quote': caption}})
    return {'schema_version': 1, 'images': images}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','metadata','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();value=build(a.inputs,a.metadata)
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if a.out.exists() and a.out.read_text()!=text:raise ValueError('caption_manifest_already_frozen')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(text,encoding='utf-8')
    print(json.dumps({'images':len(value['images']),'modality_counts':dict(Counter(i['modality'] for i in value['images'])),
                      'caption_missing':sum(not i['provenance']['quote'] for i in value['images'])}))


if __name__=='__main__':main()
