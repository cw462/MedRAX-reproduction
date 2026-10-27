# V3 image audit and frozen validation subset

This is a completed, label-free data audit, not a model evaluation. No API or model inference was used. The original split files and earlier results are unchanged. All outputs containing questions, image paths, case mappings or images remain in the private preparation workspace.

## Source and integrity

The archive is the official [ChestAgentBench figures archive at revision `921e60440927f9893228d843c0206b755744252a`](https://huggingface.co/datasets/wanglab/chest-agent-bench/blob/921e60440927f9893228d843c0206b755744252a/figures.zip). Its 822,949,819 bytes and SHA256 `8d5ac156c267046aadf54f20d961896c6e73d31ec59b8f635d1b208fa1444226` match the official Hugging Face LFS metadata. All archive-member CRC checks passed; no duplicate member names were found. There are 18,802 files in the archive. Decoding, exact-pixel and perceptual-hash checks cover all 1,346 unique images referenced by the benchmark inputs; unreferenced archive files were not all decoded.

The frozen `prepared_v2` inputs and case audit index were verified against their existing manifest before use. Neither raw answer-bearing metadata nor any label file was opened. This audit preserves the prior case-level seed `medrax-20261027`.

| Original split | Cases | Questions | Single image | Multiple images | Zero images |
|---|---:|---:|---:|---:|---:|
| memory_train | 365 | 1,500 | 732 | 768 | 0 |
| validation | 121 | 490 | 249 | 240 | 1 |
| heldout_test | 123 | 510 | 249 | 261 | 0 |
| Total | 609 | 2,500 | 1,230 | 1,269 | 1 |

All 1,346 referenced images decode successfully and none are missing. A zero-image question is still an unavailable image input, so 2,499 questions have at least one readable image. The maximum image count is 12; 95 questions have more than four images. Runners must preserve complete image bundles or report unsupported questions under the frozen denominator.

Actual encodings are 933 PNG, 412 JPEG and one single-frame GIF. For 934 referenced files the filename extension does not match the encoding, mostly `.jpg` names containing PNG data. The new validation extraction uses encoding-appropriate extensions without transcoding. Case IDs are not verified patient identifiers. The discrepancy between 609 metadata case IDs and the paper's described 675 source cases remains unresolved.

## Exact overlap and similarity candidates

Three checks answer different questions:

- **Exact bytes:** SHA256 of the original file. Two cross-split duplicate groups were found.
- **Exact canonical pixels:** SHA256 of unresized decoded RGBA pixels with width/height/mode in the hash input; no EXIF transform. This also found two cross-split groups, the same two as the byte check. Re-encoding without changing these pixels can be detected even when file bytes differ.
- **Near pHash:** grayscale Lanczos 32×32, low 8×8 DCT, median excluding DC, Hamming distance at most four. Excluding exact matches, 29 image-pair candidates were found, including one memory_train–heldout pair. These are unreviewed similarity candidates, not proof of duplicate patients or leakage, and do not cause automatic exclusion.

The two exact cross-split image groups connect the same pair of cases: one memory_train case and one heldout case, with five questions each. There are no exact cross-split validation overlaps. The existing 50-question development sample intersects neither this exact-overlap case component nor the cross-split pHash candidate cases. Its previous scores and original inputs are unchanged; this does not establish general patient independence.

## Frozen additional exclusion protocol

Before any heldout outputs, a separate private manifest was frozen with the following rule: connect whole cases through exact bytes **or** exact canonical pixels, identify connected components spanning the existing splits, and exclude the affected training cases from new memory pools. Keep the original full heldout and derive a second evaluation input excluding the whole affected heldout cases. No correctness or model outputs inform exclusion; pHash candidates are not automatically excluded.

| Evaluation or pool | Questions | Cases | Interpretation |
|---|---:|---:|---|
| Original memory_train | 1,500 | 365 | Original frozen split retained |
| New memory-pool-eligible input | 1,495 | 364 | One exact-overlap training case excluded |
| Original heldout_test | 510 | 123 | Full original denominator retained, overlap flagged |
| Additional exact-overlap-excluded heldout | 505 | 122 | One whole heldout case excluded |

The private filename `heldout_clean.inputs.jsonl` means only that confirmed exact-image-overlap cases were removed. It does **not** certify absence of all leakage, near duplicates, patient overlap or foundation-model pretraining overlap. Future full and derived evaluations require separately reported denominators. Missing, failed, invalid and unrun outcomes remain explicit; successful-only accuracy is not the primary estimate.

The exclusion-manifest SHA256 is `665ee67f9fd62a8739997e48637a31771f0d76a8382dae53ed8ab0851e6b98c1`. Its derived-input hashes are:

- New memory-pool-eligible input: `f6004c23773cd8e201b2695536e4b6f7477b7f5f36a906ec8b660b57afd5ecda`.
- Additional heldout input: `9d891c627d89a8c352509b69236d3c428248a109a92ad0865404b84e533af5bf`.

## Frozen validation30

Thirty distinct validation cases were selected without reading labels or model outputs. The eligible frame has 489 nonzero-image questions across 121 cases; the one zero-image question was explicitly recorded and excluded from this image-required development subset. All eligible images were required to be readable before selection, avoiding silent resampling around unavailable images.

Seed `20261027` controls deterministic shuffled-question tie-breaking. Selection takes one question per case, targets feasible equal single/multiple-image quotas, and greedily covers task tags derived from the visible question stem before the choices. Tags are approximate regex annotations, not official clinical categories or outcome labels. This is a coverage-oriented convenience subset, not representative stratified sampling or a heldout estimate.

The frozen subset has 15 single-image and 15 multiple-image questions: image-count distribution 1×15, 2×10, 3×4 and 4×1, totaling 51 image files and 4,667,312 bytes. It covers characterization (18), classification (2), temporal comparison (4), detection (24), diagnosis (15), localization (7), relationship (6) and unspecified (1); tags overlap, so these counts do not sum to 30. No selected case belongs to the confirmed exact-overlap component. This subset does not test inputs with more than four images.

Inference has exactly `question_id`, `question`, and `images`, with filenames relative to a separate images root. Every selected question retains all images in original order. An independent pass verified every extracted file byte-for-byte against its archive member, the 30 distinct case IDs, all frozen input/index hashes, and both whole-case exclusion outputs.

| Frozen artifact | SHA256 |
|---|---|
| validation30 inference | `ece0375215e0094b861fee867613eff2487716576e2ae1b7629df41fca5c4f76` |
| validation30 audit manifest | `175896a1d8c0ce04721a2403231671f128b1eb5297f11cff75315acf9d4fd377` |
| validation30 selection plan | `4ad73130322db1f926baf2ed7b474feed9a0cf71b005bb4c58324c389a0cedf8` |

## Reproduction and checks

New source: `data_tools/audit_figures.py` and `data_tools/freeze_validation.py`. Requirements are Python, Pillow and NumPy; no model packages are needed. They take explicit archive, frozen split, audit and output paths; output directories must be new. The full archive remains compressed during inspection, avoiding full extraction.

```bash
python data_tools/audit_figures.py --archive /private/figures.zip --split-directory /private/prepared_v2 --output /private/audit_v3 --development-audit /private/diagnostic50/audit_manifest.json
python data_tools/freeze_validation.py --archive /private/figures.zip --split-directory /private/prepared_v2 --image-audit-directory /private/audit_v3 --output /private/validation30_v3 --count 30 --seed 20261027
python -m unittest discover -s data_tools -p 'test_*.py' -v
```

All 15 data-tools tests passed: 11 new synthetic tests and four existing split tests. The new tests independently exercise re-encoded exact pixels, transitive whole-case exclusion, missing/zero-image handling, forbidden label reads, frozen hash failures, quota feasibility with shared case options, seed/order stability, and complete original image bundles. Synthetic fixtures are not real model or clinical validation results. File separation and audited readers do not by themselves provide operating-system isolation for future inference/scoring.
