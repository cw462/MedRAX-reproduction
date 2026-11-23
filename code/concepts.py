#!/usr/bin/env python3
"""Concept lexicon for chest-radiography benchmark questions."""
import re

FINDINGS = [
 "pleural effusion","pneumothorax","pneumomediastinum","hydropneumothorax","tension pneumothorax",
 "cardiomegaly","cardiac enlargement","enlarged heart","cardiac silhouette","pericardial effusion",
 "atelectasis","pulmonary atelectasis","lobar atelectasis","collapse","consolidation","pulmonary consolidation",
 "pulmonary edema","pulmonary congestion","interstitial edema","pulmonary fibrosis","interstitial fibrosis",
 "pulmonary nodule","lung nodule","nodule","pulmonary mass","mass","lung mass","opacity","pulmonary opacity",
 "infiltrate","infiltration","ground glass","ground-glass opacity","reticulation","honeycombing",
 "emphysema","hyperinflation","bronchiectasis","bronchial wall thickening","bronchial thickening",
 "hilar lymphadenopathy","hilar enlargement","lymphadenopathy","mediastinal widening","mediastinal mass",
 "aortic aneurysm","aortic dilatation","aortic calcification","tortuous aorta","aortic knob","calcified aorta",
 "granuloma","calcification","pleural thickening","pleural plaque","pleural calcification","pleural disease",
 "fracture","rib fracture","clavicle fracture","vertebral fracture","scoliosis","kyphosis","osteopenia",
 "osteoporosis","degenerative change","spondylosis",
 "indwelling catheter","central venous catheter","pulmonary artery catheter","nasogastric tube",
 "endotracheal tube","chest tube","thoracostomy tube","pacemaker","pacemaker lead","prosthetic valve",
 "sternotomy wires","surgical clips","stent","port-a-cath","hardware","foreign body","medical device",
 "lesion","cyst","cavity","cavitation","abscess","empyema","asbestosis","sarcoidosis","tuberculosis",
 "metastasis","metastases","malignancy","tumor","tumour","cancer","carcinoma","pneumonia","bronchitis",
 "asthma","copd","chronic obstructive pulmonary disease","pulmonary embolism","infarction",
 "diaphragm","hemidiaphragm","flattened diaphragm","elevated hemidiaphragm","free air",
 "pneumoperitoneum","subdiaphragmatic air","hiatal hernia","bowel obstruction","aortic dissection",
 "pulmonary hypertension","heart failure","congestive heart failure","cardiogenic shock",
 "effusion","enlargement","vascularity","vasculature","opacification","scaring","scarring","volume loss",
 "peripheral opacity","central opacity","air space opacity","airspace disease","interstitial pattern",
 "reticular pattern","nodular pattern","miliary pattern","cavitating lesion","solitary pulmonary nodule",
]

ANATOMY = [
 "heart","lung","lungs","liver","kidney","kidneys","spleen","bladder","bowel","stomach","abdomen",
 "thorax","chest","mediastinum","hilum","hila","pleura","ribs","spine","clavicle","shoulder","neck",
 "airway","trachea","bronchus","bronchi","heart size","pulmonary vasculature","vascular markings",
]

PROCEDURE = ["x-ray","ct","mri","ultrasound","radiograph","scan","study","image","picture","film","contrast"]

def _norm(t):
    return " " + re.sub(r"[^a-z0-9 ]", " ", t.lower()) + " "

def find_concepts(text, vocab):
    """Longest-match concepts present in text. Returns list of (concept, kind)."""
    s = _norm(text)
    hits = []
    for term, kind in vocab:
        if " " + term + " " in s:
            hits.append((term, kind))
    # drop terms fully contained in a longer matched term
    hits.sort(key=lambda x: -len(x[0]))
    kept = []
    for term, kind in hits:
        if not any(" " + term + " " in " " + k + " " for k, _ in kept):
            kept.append((term, kind))
    return kept

_VOCAB = [(t, "finding") for t in FINDINGS] + [(t, "anatomy") for t in ANATOMY] + [(t, "procedure") for t in PROCEDURE]
_VOCAB.sort(key=lambda x: -len(x[0]))

def concept_for(question, options):
    """Return (concept, kind) using question + options only (no gold answer)."""
    text = question
    if options:
        text += " " + " ".join(str(v) for v in options.values())
    hits = find_concepts(text, _VOCAB)
    for term, kind in hits:
        if kind == "finding":
            return term, kind
    if hits:
        return hits[0][0], hits[0][1]
    return None, None