set -u
cd /home/imss/cw/radiology_rag_p3
PY=/home/imss/miniconda3/envs/mineru/bin/python

for arm in A B; do
  for a in $(seq 1 15); do
    $PY -u loc_arm.py $arm loc_arm${arm}.jsonl > loc_arm${arm}.log 2>&1
    rc=$?
    tail -1 loc_arm${arm}.log
    [ $rc -eq 0 ] && break
    echo "arm$arm attempt $a rc=$rc"; sleep 10
  done
done

echo "=== eval ==="
for a in 1 2 3 4 5; do
  $PY - > loc_eval.txt 2>&1 <<'PYEOF'
import json
m5 = {json.loads(l)["question_id"]: json.loads(l)
      for l in open("m5_chexbench.jsonl", encoding="utf-8-sig") if l.strip()}
for arm in ("A", "B"):
    rows = [json.loads(l) for l in open(f"loc_arm{arm}.jsonl") if l.strip()]
    ok = sum(1 for x in rows if x["letter"] == m5[x["qid"]]["reference"])
    print(f"arm {arm}: n={len(rows)} correct={ok} ({100*ok/max(1,len(rows)):.1f}%)")
# per-question B vs A
A = {x["qid"]: x for x in [json.loads(l) for l in open("loc_armA.jsonl") if l.strip()]}
B = {x["qid"]: x for x in [json.loads(l) for l in open("loc_armB.jsonl") if l.strip()]}
diff = 0; fix = brk = 0
for q in sorted(A):
    ref = m5[q]["reference"]
    a_ok = A[q]["letter"] == ref
    b_ok = B[q]["letter"] == ref
    if A[q]["letter"] != B[q]["letter"]:
        diff += 1
        if not a_ok and b_ok: fix += 1
        if a_ok and not b_ok: brk += 1
print(f"changed answers: {diff}  (geometry fixed {fix}, broke {brk})")
PYEOF
  rc=$?
  [ $rc -eq 0 ] && break
  sleep 8
done
cat loc_eval.txt
