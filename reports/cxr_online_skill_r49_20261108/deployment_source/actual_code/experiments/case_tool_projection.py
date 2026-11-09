"""Fixed tool attribution and strong-signal projection; no reference access."""
import re

CLASSIFIER='chest_xray_classifier'
REPORT='chest_xray_report_generator'
ALIASES={
 'Atelectasis':r'atelecta', 'Consolidation':r'consolidat', 'Infiltration':r'infiltrat',
 'Pneumothorax':r'pneumothora', 'Edema':r'edema|oedema', 'Emphysema':r'emphysema',
 'Fibrosis':r'fibros', 'Effusion':r'effusion', 'Pneumonia':r'pneumonia',
 'Pleural_Thickening':r'pleural thickening', 'Cardiomegaly':r'cardiomegaly|cardiac silhouette is enlarged|enlarged heart',
 'Nodule':r'nodule|nodular', 'Mass':r'\bmass(?:es)?\b', 'Hernia':r'hernia',
 'Lung Lesion':r'lung lesion|pulmonary lesion', 'Fracture':r'fracture',
 'Lung Opacity':r'opaci', 'Enlarged Cardiomediastinum':r'widened mediastinum|mediastinal widening|enlarged cardiomediast',
}


def positive_report_spans(text, finding):
    pattern=ALIASES.get(finding, re.escape(finding.replace('_',' ')))
    spans=[]
    for sentence in re.split(r'[.;\n]+', text):
        for clause in re.split(r'\bbut\b|\bhowever\b',sentence,flags=re.I):
            if (re.search(pattern,clause,re.I)
                    and not re.search(r'\bno\b|\bnot\b|without|negative for|absence of|resolved|cannot exclude|can\W?t exclude|possible|questionable',clause,re.I)):
                spans.append(clause.strip())
    return spans


def project_evidence(evidence, variant, threshold=.8):
    if variant not in ('classifier','report','combined') or threshold != .8:
        raise ValueError('fixed_E3_projection_required')
    projected=[]
    for image in evidence['evidence_for_model']['images']:
        hypotheses={h['tool']:h['result'] for h in image['tool_hypotheses']}
        strong={}
        raw=hypotheses.get(CLASSIFIER)
        if isinstance(raw,(tuple,list)) and raw and isinstance(raw[0],dict):
            strong={k:float(v) for k,v in raw[0].items() if isinstance(v,(int,float)) and not isinstance(v,bool) and threshold<=v<=1}
        raw=hypotheses.get(REPORT)
        report=raw[0] if isinstance(raw,(tuple,list)) and raw and isinstance(raw[0],str) else ''
        item={'source_filename':image['source_filename'],'modality':'CXR','tool_hypotheses':[]}
        if variant in ('classifier','combined') and strong:
            item['tool_hypotheses'].append({'tool':CLASSIFIER,'strong_findings':strong,
                'score_scale':'XRV operating-point normalized score, not calibrated probability','threshold':threshold})
        if variant in ('report','combined') and report.strip():
            item['tool_hypotheses'].append({'tool':REPORT,'report':report})
        if variant=='combined' and strong and report:
            item['positive_tool_agreement']=[{'finding':k,'classifier_score':v,'report_spans':spans}
                for k,v in strong.items() if (spans:=positive_report_spans(report,k))]
            item['agreement_note']='Conservative lexical positive-assertion agreement only, not verified truth; absent agreement is not disagreement.'
        if item['tool_hypotheses']:projected.append(item)
    return {'status':'UNVERIFIED_TOOL_EVIDENCE' if projected else 'NO_EVIDENCE',
            'variant':variant,'classifier_strong_threshold':threshold,
            'limitations':evidence['evidence_for_model']['limitations'], 'images':projected}
