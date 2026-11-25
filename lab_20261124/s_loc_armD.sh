set -u
cd /home/imss/cw/radiology_rag_p3
PY=/home/imss/miniconda3/envs/mineru/bin/python
for a in $(seq 1 15); do
  $PY -u loc_arm.py D loc_armD.jsonl > loc_armD.log 2>&1
  rc=$?
  tail -1 loc_armD.log
  [ $rc -eq 0 ] && break
  echo "armD attempt $a rc=$rc"; sleep 10
done
$PY - > loc_eval4.txt 2>&1 <<'PYEOF'
import json
m5 = {json.loads(l)["question_id"]: json.loads(l)
      for l in open("m5_chexbench.jsonl", encoding="utf-8-sig") if l.strip()}
def dedupe(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        x = json.loads(line)
        if x["qid"] not in rows or (rows[x["qid"]]["letter"] in "!?" and x["letter"] not in "!?"):
            rows[x["qid"]] = x
    return rows
A = dedupe("loc_armA.jsonl")
D = dedupe("loc_armD.jsonl")
common = sorted(set(A) & set(D))
ref = {q: m5[q]["reference"] for q in common}
a_ok = sum(1 for q in common if A[q]["letter"] == ref[q])
d_ok = sum(1 for q in common if D[q]["letter"] == ref[q])
print(f"arm A: {a_ok}/{len(common)} = {100*a_ok/len(common):.1f}%")
print(f"arm D: {d_ok}/{len(common)} = {100*d_ok/len(common):.1f}%")
for label, base in (("all", common), ("M5 errors", [q for q in common if not m5[q].get("correct")])):
    fix = brk = 0
    for q in base:
        if A[q]["letter"] != D[q]["letter"]:
            d_c = D[q]["letter"] == ref[q]
            a_c = A[q]["letter"] == ref[q]
            if not a_c and d_c:
                fix += 1
            if a_c and not d_c:
                brk += 1
    print(f"D vs A on {label}: fixed {fix}, broke {brk}, net {fix-brk}")
PYEOF
cat loc_eval4.txt
echo ALL_DONE
