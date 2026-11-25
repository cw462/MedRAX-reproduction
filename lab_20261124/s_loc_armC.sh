set -u
cd /home/imss/cw/radiology_rag_p3
PY=/home/imss/miniconda3/envs/mineru/bin/python
for a in $(seq 1 15); do
  $PY -u loc_arm.py C loc_armC.jsonl > loc_armC.log 2>&1
  rc=$?
  tail -1 loc_armC.log
  [ $rc -eq 0 ] && break
  echo "armC attempt $a rc=$rc"; sleep 10
done
echo "=== eval C vs A vs B (deduped) ==="
for a in 1 2 3 4 5; do
  $PY - > loc_eval3.txt 2>&1 <<'PYEOF'
import json
m5 = {json.loads(l)["question_id"]: json.loads(l)
      for l in open("m5_chexbench.jsonl", encoding="utf-8-sig") if l.strip()}
def dedupe(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        x = json.loads(line)
        if x["qid"] not in rows or (rows[x["qid"]]["letter"] in "!?" and x["letter"] not in "!?"):
            rows[x["qid"]] = x
    return rows
A = dedupe("loc_armA.jsonl"); B = dedupe("loc_armB.jsonl"); C = dedupe("loc_armC.jsonl")
common = sorted(set(A) & set(B) & set(C))
ref = {q: m5[q]["reference"] for q in common}
for name, D in (("A", A), ("B", B), ("C", C)):
    ok = sum(1 for q in common if D[q]["letter"] == ref[q])
    print(f"arm {name}: {ok}/{len(common)} = {100*ok/len(common):.1f}%")
# C vs A on all; C vs A on M5 errors
for base in (("all", common), ("M5 errors", [q for q in common if not m5[q].get("correct")])):
    fix = brk = 0
    for q in base[1]:
        if A[q]["letter"] != C[q]["letter"]:
            c_ok = C[q]["letter"] == ref[q]
            a_ok = A[q]["letter"] == ref[q]
            if not a_ok and c_ok: fix += 1
            if a_ok and not c_ok: brk += 1
    print(f"C vs A on {base[0]}: fixed {fix}, broke {brk}, net {fix-brk}")
PYEOF
  rc=$?
  [ $rc -eq 0 ] && break
  sleep 8
done
cat loc_eval3.txt
