set -u
/root/miniconda3/bin/python - <<'PYEOF'
import json, re
from collections import Counter

tasks = {t['qid']: t for t in json.load(open('/dev/shm/lat_tasks_maira.json'))}
reports = json.load(open('/dev/shm/maira_reports.json'))
p0 = {r['qid']: r for r in json.load(open('/root/p0_side_result.json'))}
side = [q for q in tasks if tasks[q]['kind'] == 'side']

def sides(text):
    w = set(re.findall(r'[a-z]+', text.lower()))
    return {x for x in w if x in ('left', 'right')}

def report_side(q):
    """Return (side, confidence) or (None, None)."""
    t = tasks[q]
    rep = reports.get(t['image']) or {}
    kw = t['phrase'].split()[-1].lower().rstrip('.,')
    # strict: sentence about the finding, exactly one side
    for s in (rep.get('sentences') or []):
        if kw in s['text'].lower():
            sw = sides(s['text'])
            if len(sw) == 1:
                return sw.pop(), 'strict'
            if len(sw) == 2:
                # both sides in one sentence: use the box of that sentence if any
                bx = s.get('boxes') or []
                if bx:
                    b = bx[0]['norm']
                    return ('right' if (b[0]+b[2])/2 < 0.5 else 'left'), 'ambig_box'
                return None, None
    # loose: whole report mentions exactly one side
    sw = sides(rep.get('raw', ''))
    if len(sw) == 1:
        return sw.pop(), 'loose'
    return None, None

pred = {q: report_side(q) for q in side}

print('=== coverage by confidence ===')
print(Counter(c for _s, c in pred.values()))

eval_q = [q for q in side if q in p0]
print(f'\nevaluable vs M5: {len(eval_q)}')

def m5_ok(q):
    return bool(p0[q]['okA'])

base = sum(1 for q in eval_q if m5_ok(q)) / len(eval_q)
print(f'M5 baseline on these: {100*base:.1f}%')

for name, allowed in [
    ('strict only', {'strict'}),
    ('strict+ambig_box', {'strict', 'ambig_box'}),
    ('all (loose incl.)', {'strict', 'ambig_box', 'loose'}),
]:
    cov = [q for q in eval_q if pred[q][1] in allowed]
    ok = 0
    for q in eval_q:
        s, c = pred[q]
        if c in allowed and s:
            ok += (s == tasks[q]['gold_attr'])
        else:
            ok += m5_ok(q)
    racc = sum(1 for q in cov if pred[q][0] == tasks[q]['gold_attr'])
    print(f'\n{name}: coverage {len(cov)}/{len(eval_q)} ({100*len(cov)/len(eval_q):.1f}%)')
    print(f'  report acc on covered: {100*racc/max(1,len(cov)):.1f}%')
    print(f'  HYBRID total: {100*ok/len(eval_q):.1f}%  (M5 {100*base:.1f}%, delta {100*ok/len(eval_q)-100*base:+.1f})')

# agreement analysis on strict coverage
strict = [q for q in eval_q if pred[q][1] == 'strict']
agree = [q for q in strict if (pred[q][0] == 'right') == m5_ok(q) and False]
print('\n=== agreement table (strict subset) ===')
def m5_side(q):
    # map M5 letter prediction to a side using option diff
    t = tasks[q]
    pr = str(p0[q]['predA']).strip().upper()
    if pr == 'A': return t['diff_a']
    if pr == 'B': return t['diff_b']
    return None
tab = Counter()
for q in strict:
    rs = pred[q][0]; ms = m5_side(q)
    same = rs == ms
    tab[(same, rs == tasks[q]['gold_attr'], m5_ok(q))] += 1
for k, v in sorted(tab.items()):
    print(f'  agree={k[0]} report_ok={k[1]} m5_ok={k[2]}: {v}')
both = [q for q in strict if m5_side(q) == pred[q][0]]
if both:
    print(f'  when agree (n={len(both)}): acc={100*sum(1 for q in both if m5_ok(q))/len(both):.1f}%')
dis = [q for q in strict if m5_side(q) != pred[q][0]]
if dis:
    print(f'  when disagree (n={len(dis)}): report acc={100*sum(1 for q in dis if pred[q][0]==tasks[q]["gold_attr"])/len(dis):.1f}%  m5 acc={100*sum(1 for q in dis if m5_ok(q))/len(dis):.1f}%')
PYEOF
