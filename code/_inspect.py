import sys, json
sys.path.insert(0, "rag_eval")
import index
idx = index.load()
for q in ["Can effusion be observed on the lower left lung in this picture?",
          "Is there evidence of an aortic aneurysm?",
          "Is the heart abnormally large?"]:
    print("=" * 10, q)
    for d in index.search(idx, q, 3):
        print("  [%s] %s" % (d["source"], d["title"][:80]))
        print("      " + d["contents"][:180].replace("\n", " "))
