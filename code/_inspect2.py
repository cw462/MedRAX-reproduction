import sys
sys.path.insert(0, "rag_eval")
import index
idx = index.load()
qs = ["Can effusion be observed on the lower left lung in this picture?",
      "Is there evidence of an aortic aneurysm?",
      "Is the heart abnormally large?",
      "Are the bronchial airways enlarged?",
      "is there hylar lymphadenopathy?"]
for q in qs:
    print("=" * 8, q)
    for d in index.search(idx, q, 3):
        print("  %.1f [%s] %s" % (d["score"], d["source"], d["title"][:90]))
        print("        " + d["contents"][:170].replace("\n", " "))
