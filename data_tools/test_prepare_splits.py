import copy
import unittest

from prepare_splits import build


def sample():
    return [{"case_id": str(i // 2), "question_id": f"q{i}", "question": "Choose A or B",
             "images": [f"figures/{i // 2}/image.jpg"],
             "image_source_urls": [f"https://example.test/{i // 2}"],
             "answer": "A", "explanation": "SECRET EXPLANATION", "sections": "SECRET SECTIONS"}
            for i in range(10)]


class SplitTest(unittest.TestCase):
    def test_reproducible_and_label_isolated(self):
        records, labels, manifest = build(sample(), "seed")
        records2, labels2, manifest2 = build(list(reversed(sample())), "seed")
        self.assertEqual((records, labels, manifest), (records2, labels2, manifest2))
        self.assertEqual(sum(map(len, records.values())), 10)
        for split, group in records.items():
            for record in group:
                self.assertEqual(set(record), {"question_id", "question", "images"})
            self.assertEqual({x["question_id"] for x in group}, {x["question_id"] for x in labels[split]})
            for label in labels[split]:
                self.assertEqual(set(label), {"question_id", "answer"})
        self.assertNotIn("SECRET", repr(records))

    def test_missing_case_and_duplicate_question_fail(self):
        rows = sample()
        del rows[0]["case_id"]
        with self.assertRaises(ValueError):
            build(rows, "seed")
        rows = sample()
        rows[1]["question_id"] = rows[0]["question_id"]
        with self.assertRaises(ValueError):
            build(rows, "seed")

    def test_duplicate_image_cross_split_fails(self):
        rows = sample()
        inputs, _, _ = build(rows, "seed")
        split_lookup = {r["question_id"]: s for s, rr in inputs.items() for r in rr}
        first = rows[0]
        other = next(r for r in rows if split_lookup[r["question_id"]] != split_lookup[first["question_id"]])
        other["images"] = copy.copy(first["images"])
        with self.assertRaisesRegex(ValueError, "same image path"):
            build(rows, "seed")

    def test_unexpected_nested_images_fail(self):
        rows = sample()
        rows[0]["images"] = [["path"]]
        with self.assertRaisesRegex(ValueError, "flat list"):
            build(rows, "seed")


if __name__ == "__main__":
    unittest.main()
