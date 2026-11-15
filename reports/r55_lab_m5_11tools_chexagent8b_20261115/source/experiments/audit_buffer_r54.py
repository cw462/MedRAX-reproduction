"""Read-only offline audit of old R49 traces; does not build a library or claim gain."""
import argparse,json
from pathlib import Path
from collections import Counter
from skill_policy_r54 import eligibility
from skill_lifecycle_r49 import gate
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    ts=[json.loads(p.read_text()) for p in a.run.glob('windows/*/trajectories/*.json')]
    print(json.dumps({'questions':len(ts),'old_gate_eligible':sum(gate(t) for t in ts),
        'new_gate_eligible':sum(eligibility(t)[0] for t in ts),
        'new_reasons':dict(Counter(eligibility(t)[1] for t in ts)),
        'paid_calls':0,'skills_created':0,'new_accuracy':None},ensure_ascii=False,indent=2))
