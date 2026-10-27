# Development diagnosis: report decoder termination

Five fixed, different memory-train cases were evaluated with all four decoding variants, without API requests or reference answers. Models, image bytes, preprocessing, FP32 weights and max_length=128 were held constant. The source checkout was unchanged; `experiments/report_parameter_ablation.py` uses an explicit subclass to vary GenerationConfig construction.

| Variant | Effective beams | EOS | Report text identical to each image's upstream output | Returned sequence lengths, two sections × five images |
|---|---:|---|---:|---:|
| Upstream | 1 (`beam_width=2` ignored by beam selection) | None | 5/5 | 1280 total; all 10 reached 128 |
| Beams only | 2 (`num_beams=2`) | None | 0/5 | 1280 total; all 10 reached 128 |
| EOS only | 1 | Decoder EOS, verified equal to tokenizer SEP | 5/5 | 361 total; none reached 128; all 10 contained configured EOS |
| Beams + EOS | 2 | Decoder EOS, verified equal to tokenizer SEP | 0/5 | 386 total; none reached 128; all 10 contained configured EOS |

EOS-only returned lengths were 31, 34, 39, 7, 30, 26, 63, 23, 76 and 32. These include special/start tokens; they are not report word counts or API-billed tokens. The five image-specific report hashes are different from one another. Equality means each image's EOS-only text matched its own original report, not that all images produced the same report.

Mean observed per-image inference times were upstream 0.569 s, beams-only 0.565 s, EOS-only 0.164 s and beams+EOS 0.236 s. The fixed run order and first upstream inference (1.030 s, versus roughly 0.45 s subsequently) confound timing with warm-up. These are one-pass observations, not a reliable speedup benchmark or evidence that beam search is faster. A later performance claim needs warm-up, randomized order and repeated measurements.

The first upstream report exactly matched two earlier independent smoke invocations: image digest `457b31de0e8869b26ef5fc91e6f2874d2bcce42b963e9d8df896e43a52491919`, report digest `3e2e3a78ddd3a73dad4d372ed9e5090aa45b93cb958616049ad0b1ec45b583d3`, 389 characters. Model assets and original tool source hashes also matched. Independent review confirmed all 20 combinations, source-runner hash, image alignment and per-image text equality.

This supports an engineering hypothesis: setting the decoder's own EOS may avoid unnecessary continuation while preserving visible text on this development sample. It does not establish clinical accuracy, semantic completeness, broad text equivalence or full-paper performance. Beam changes alter outputs and must be treated as a separate behavior change. The original Agent baseline remains unchanged.

Run with complete fixed local model assets and a new output directory:

```sh
python experiments/report_parameter_ablation.py --repo /path/to/MedRAX \
  --input /path/to/inference.jsonl --images-root /path/to/images \
  --cache-dir /path/to/fixed-hf-cache --output /path/to/new-run \
  --device cuda:0 --max-cases 5
```

Complete generated report strings remain in ignored private output directories. This experiment performs no scoring and cannot read labels through its input schema.
