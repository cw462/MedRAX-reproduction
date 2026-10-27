"""Synthetic-only invariants for image audit and whole-case exclusions."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from PIL import Image

try:
    from . import audit_figures as audit
except ImportError:
    import audit_figures as audit


def png(color, compression=6):
    image = Image.new("RGB", (19, 13), color)
    image.putpixel((5, 3), (255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=compression)
    return stream.getvalue()


def fixture(root, *, missing=False):
    split_root = root/"splits"; split_root.mkdir()
    image_bytes = {
        "figures/t1/image.jpg": png((30, 40, 50), 0),
        "figures/h1/image.png": png((30, 40, 50), 9),
        "figures/other/a.png": png((10, 70, 130)),
        "figures/other/b.png": png((90, 80, 70)),
        "figures/other/c.png": png((110, 20, 30)),
        "figures/other/d.png": png((0, 10, 200)),
        "figures/other/e.png": png((180, 10, 90)),
    }
    mapping = {
        "memory_train": [("t1a", "case_t1", ["figures/t1/image.jpg"]),
                         ("t1b", "case_t1", ["figures/other/a.png"]),
                         ("t2", "case_t2", ["figures/other/b.png"])],
        "validation": [("v1", "case_v1", ["figures/other/c.png"]),
                       ("v2", "case_v2", ["figures/other/c.png", "figures/other/d.png"]),
                       ("v3a", "case_v3", ["figures/other/d.png"]),
                       ("v3b", "case_v3", ["figures/other/d.png", "figures/other/e.png"]),
                       ("v0", "case_v0", [])],
        "heldout_test": [("h1a", "case_h1", ["figures/h1/image.png"]),
                         ("h1b", "case_h1", ["figures/other/a.png"]),
                         ("h2", "case_h2", ["figures/other/e.png"])],
    }
    # All unique other images are split-disjoint; sharing within validation is
    # deliberate, but the h1b-only image has the same case-level exclusion.
    image_bytes["figures/h1/second.png"] = png((21, 32, 43))
    image_bytes["figures/h2/image.png"] = png((71, 12, 99))
    mapping["heldout_test"][1] = ("h1b", "case_h1", ["figures/h1/second.png"])
    mapping["heldout_test"][2] = ("h2", "case_h2", ["figures/h2/image.png"])
    rows, index = {}, []
    for split, entries in mapping.items():
        rows[split] = [{"question_id": qid,
                        "question": "Where is the abnormality and what is the likely diagnosis?\nA. First\nB. Second",
                        "images": images} for qid, case, images in entries]
        index.extend({"question_id": qid, "case_hash": case, "split": split} for qid, case, images in entries)
        audit.write_jsonl(split_root/(split+".inputs.jsonl"), rows[split])
        # Deliberately invalid label contents: successful parsing would fail if
        # any audit or selection path attempted to consume this file.
        (split_root/(split+".labels.jsonl")).write_text("FORBIDDEN LABEL CONTENT", encoding="utf-8")
    audit.write_jsonl(split_root/"audit_index.jsonl", index)
    names = ["audit_index.jsonl"]+[split+".inputs.jsonl" for split in audit.SPLITS]
    audit.write_json(split_root/"manifest.json", {"artifact_sha256": {name: audit.file_sha(split_root/name) for name in names},
                                                "source_sha256": "synthetic_source", "seed": "synthetic"})
    archive_path = root/"figures.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path, data in image_bytes.items():
            if missing and path == "figures/other/c.png":
                continue
            archive.writestr(path, data)
    return split_root, archive_path, image_bytes


def run_audit(root, *, missing=False):
    split_root, archive, images = fixture(root, missing=missing)
    output = root/"audit"
    with contextlib.redirect_stdout(io.StringIO()):
        summary = audit.audit_archive(archive, split_root, output,
                                      expected_sha256=audit.file_sha(archive), expected_bytes=archive.stat().st_size)
    return split_root, archive, images, output, summary


class ImageAuditTest(unittest.TestCase):
    def test_reencoding_detects_pixels_not_bytes_and_preserves_shape(self):
        a, b = png((30, 40, 50), 0), png((30, 40, 50), 9)
        self.assertNotEqual(audit.sha(a), audit.sha(b))
        first, second = audit.inspect_image(a), audit.inspect_image(b)
        self.assertEqual(first["canonical_pixel_sha256"], second["canonical_pixel_sha256"])
        self.assertEqual((first["width"], first["height"]), (19, 13))
        self.assertNotEqual(first["canonical_pixel_sha256"], audit.inspect_image(png((30, 40, 51)))["canonical_pixel_sha256"])

    def test_audit_whole_case_exclusion_and_labels_never_opened(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original_open = Path.open
            opened = []
            def guarded(path, mode="r", *args, **kwargs):
                if "r" in mode:
                    opened.append(path.name)
                    if ".labels." in path.name:
                        self.fail("Forbidden label read")
                return original_open(path, mode, *args, **kwargs)
            with mock.patch.object(Path, "open", guarded):
                split_root, archive, images, output, summary = run_audit(root)
            excluded = audit.read_json(output/"leakage_exclusion_manifest.json")
            self.assertEqual(summary["cross_split_exact_byte_groups"], 0)
            self.assertEqual(summary["cross_split_exact_pixel_groups"], 1)
            self.assertEqual(excluded["excluded_question_ids_by_split"]["memory_train"], ["t1a", "t1b"])
            self.assertEqual(excluded["excluded_question_ids_by_split"]["heldout_test"], ["h1a", "h1b"])
            self.assertEqual([r["question_id"] for r in audit.read_jsonl(output/"heldout_clean.inputs.jsonl")], ["h2"])
            self.assertEqual(len(audit.read_jsonl(split_root/"heldout_test.inputs.jsonl")), 3)
            self.assertFalse(excluded["phash_used_for_exclusion"])
            self.assertTrue(summary["all_member_crc_checked"])
            self.assertIsNone(summary["first_bad_crc_member"])
            self.assertIn("heldout_test.inputs.jsonl", opened)

    def test_transitive_case_linkage_not_near_similarity(self):
        def row(path, case, byte, pixel):
            return {"dataset_image_path": path, "case_hashes": [case], "splits": ["memory_train"],
                    "question_ids": [case], "sha256": byte, "canonical_pixel_sha256": pixel, "phash": "00"}
        records = [row("a", "a", "one", "pixel_one"), row("b", "b", "two", "pixel_one"),
                   row("b2", "b", "three", "pixel_three"), row("c", "c", "three", "pixel_four"),
                   row("d", "d", "four", "pixel_five")]
        components, _ = audit.exact_case_components(records)
        self.assertEqual(components, [["a", "b", "c"]])

    def test_missing_is_reported_and_zero_images_not_counted_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, output, summary = run_audit(Path(temp), missing=True)
            self.assertEqual(summary["referenced_image_status_counts"]["missing"], 1)
            rows = {r["question_id"]: r for r in audit.read_jsonl(output/"question_image_audit.jsonl")}
            self.assertFalse(rows["v1"]["all_images_readable"])
            self.assertTrue(rows["v0"]["no_images"])
            self.assertFalse(rows["v0"]["all_images_readable"])

    def test_frozen_hash_and_archive_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            split_root, archive, _ = fixture(root)
            with self.assertRaisesRegex(ValueError, "expected pinned"):
                audit.audit_archive(archive, split_root, root/"out", expected_sha256="0"*64, expected_bytes=archive.stat().st_size)
            path = split_root/"validation.inputs.jsonl"
            path.write_text(path.read_text()+"\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit.load_splits(split_root)


if __name__ == "__main__":
    unittest.main()
