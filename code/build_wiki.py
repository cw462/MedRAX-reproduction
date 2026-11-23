#!/usr/bin/env python3
"""Build radiology knowledge corpus from Wikipedia plaintext (one title per request)."""
import json, ssl, sys, time, urllib.parse, urllib.request

OUT = r"H:/RAG_KB/corpus_wiki.jsonl"
API = "https://en.wikipedia.org/w/api.php"
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http":"http://127.0.0.1:7897","https":"http://127.0.0.1:7897"}),
                                 urllib.request.HTTPSHandler(context=ctx))
OP.addheaders = [("User-Agent","RadiologyRAGResearch/0.1 (academic; contact: local)")]

TITLES = """Cardiomegaly|Pleural effusion|Pneumothorax|Atelectasis|Pulmonary consolidation|Pulmonary edema|Pulmonary fibrosis|Lung nodule|Pulmonary mass|Bronchiectasis|Emphysema|Chronic obstructive pulmonary disease|Pneumonia|Tuberculosis|Lung cancer|Pulmonary embolism|Aortic aneurysm|Aortic dissection|Thoracic aorta|Mediastinum|Cardiothoracic ratio|Chest radiograph|Radiography|Radiology|Interstitial lung disease|Ground-glass opacity|Honeycombing|Pleural thickening|Asbestosis|Mesothelioma|Empyema|Pleural cavity|Costophrenic angle|Hemothorax|Pneumomediastinum|Subcutaneous emphysema|Rib fracture|Clavicle fracture|Scoliosis|Kyphosis|Osteoporosis|Osteopenia|Diaphragmatic hernia|Hiatal hernia|Pneumoperitoneum|Bowel obstruction|Central venous catheter|Nasogastric intubation|Endotracheal tube|Chest tube|Artificial cardiac pacemaker|Prosthetic heart valve|Coronary stent|Foreign body|Medical imaging|Computed tomography|Magnetic resonance imaging|Medical ultrasound|Mammography|Heart failure|Myocardial infarction|Pericardial effusion|Pericarditis|Cardiac tamponade|Hypertrophic cardiomyopathy|Dilated cardiomyopathy|Pulmonary hypertension|Cor pulmonale|Sarcoidosis|Cystic fibrosis|Asthma|Acute respiratory distress syndrome|Lobar pneumonia|Lung abscess|COVID-19|Influenza|Histoplasmosis|Silicosis|Hypersensitivity pneumonitis|Trachea|Bronchus|Lung|Pleura|Pericardium|Heart|Aorta|Pulmonary artery|Superior vena cava|Esophagus|Stomach|Liver|Spleen|Kidney|Abdomen|Pelvis|Metastasis|Neoplasm|Cancer|Sepsis|Fracture|Osteomyelitis|Paget's disease of bone|Anemia|Lymphoma|Breast cancer|Adenopathy|Lymphadenopathy|Hilum of lung|Radiodensity|Hounsfield scale|Radiocontrast agent|X-ray|Fluoroscopy|Pneumatosis|Air bronchogram|Silhouette sign|Kerley lines|Cephalization|Bat wing appearance|Tree-in-bud sign|Halo sign|Crazy paving|Signet ring sign|Golden S sign|Deep sulcus sign|Continuous diaphragm sign|Fleischner sign|Hampton's hump|Westermark sign|Snowstorm appearance|Eggshell calcification|Popcorn calcification|Sunburst appearance|Codman triangle|Onion skin periosteal reaction|Lytic lesion|Sclerotic lesion|Bone tumor|Rickets|Fibrous dysplasia|Giant cell tumor of bone|Osteochondroma|Enchondroma|Pneumonia|Pulmonary aspiration|Bronchiolitis|Respiratory failure|Hypoxia (medicine)|Hyperinflation|Atelectasis|Pleural effusion|Pneumothorax|Pulmonary edema|Cardiomegaly|Tracheal deviation|Mediastinal shift|Tension pneumothorax|Flail chest|Rib cage|Thorax|Chest injury|Pulmonary contusion|Aortic rupture|Diaphragmatic rupture|Pneumopericardium|Chylothorax|Thoracentesis|Bronchoscopy|Mechanical ventilation|Intensive care unit|Ventilator-associated pneumonia|Sepsis|Septic shock|Multiple organ dysfunction syndrome|Cancer staging|TNM staging system|RECIST"""

def fetch(title):
    params = {"action": "query", "prop": "extracts", "explaintext": 1, "format": "json",
              "redirects": 1, "exlimit": 1, "titles": title}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with OP.open(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                time.sleep(6 + attempt * 4)
                continue
            raise
    return None

def main():
    titles = list(dict.fromkeys(t.strip() for t in TITLES.split("|") if t.strip()))
    print("titles:", len(titles), flush=True)
    docs, missing = [], 0
    for i, t in enumerate(titles, 1):
        try:
            d = fetch(t)
        except Exception as e:
            print("fail", t, str(e)[:80]); continue
        if not d:
            missing += 1; continue
        for pid, page in d.get("query", {}).get("pages", {}).items():
            if "extract" not in page:
                missing += 1; continue
            title, text = page["title"], page["extract"]
            paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 80]
            for j, p in enumerate(paras):
                docs.append({"id": f"wiki:{title}:{j}", "source": "Wikipedia",
                             "title": title, "contents": f"{title}. {p}"})
        if i % 20 == 0:
            print(i, "docs", len(docs), "missing", missing, flush=True)
        time.sleep(0.35)
    with open(OUT, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print("saved", OUT, len(docs), "missing", missing)

if __name__ == "__main__":
    main()
