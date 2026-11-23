import sys
sys.path.insert(0, "rag_eval")
import index
idx = index.load()
for q in ["Is the heart abnormally large?", "Can effusion be observed on the lower left lung in this picture?", "Is there a pneumothorax?"]:
    print("=" * 8, q)
    for d in index.search(idx, q, 3):
        print("  [%s] %s" % (d["source"], d["title"][:60]))
        print("      " + d["contents"][:260].replace("\n", " "))
