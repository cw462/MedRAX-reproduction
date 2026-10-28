# Single-file data corruption observed on the lab server (2026-10-28)

Status: **observed, mitigated for one file, cause not established.** This is the same class
of failure the earlier V3 checkpoint recorded for large weight downloads; here it affected a
17 KB image already verified on disk.

## What happened

Timeline (server local time, Asia/Shanghai):

| time | event | evidence |
|---|---|---|
| 15:14 | 100 subset images uploaded and verified against the frozen audit | preflight printed `subset_questions_verified: 100` |
| 15:39 | training run v2 starts; all 60 preflight hashes match the frozen audit | stored `plan.records[*].images[*].sha256` re-checked later: 0 mismatches |
| 15:59 | a resume attempt rebuilds the plan and is rejected | `plan.records[16].images[0].sha256` = `e93a1746…` while the frozen value is `a58faf37…` |
| 16:03 | direct reads of the same file return `e93a1746…` four times in a row | size unchanged, 170 459 bytes, inode unchanged |
| 16:04 | a second full pass over all 100 files reports 0 mismatches | the same file read back as `a58faf37…` |
| 16:05 | five rounds over all 100 files: 1 file mismatched in 4 of 5 rounds | only `figures/11239/figure_2.jpg` |
| 16:05 | file deleted and re-uploaded from the locally verified copy | 8 consecutive reads return `a58faf37…` |

The file is `figures/11239/figure_2.jpg`, question `11239_8353800736225`. Its size never
changed, its mtime was not updated between the good and bad reads, and the corruption is a
whole-file substitution between two byte strings rather than a partial truncation. Reads
immediately after the rewrite are stable.

## Why it matters for the experiment

- `memory_pipeline` compares the run manifest's per-image SHA-256 with the frozen split
  audit. A corrupted read at preflight makes the run **uncompilable** rather than silently
  entering the pool.
- A corrupted read at tool-call time is compared against the declared question images and
  also fails compilation.
- The remaining silent risk is the image bytes encoded for the model: they are read a third
  time, after preflight. A flap exactly at that moment would show the model different pixels
  while the trace kept the good hash. Nothing in the current runner detects that; it is
  recorded here as an unquantified validity risk, not a solved problem.
- Any future run should (a) hash the exact bytes sent to the model and refuse on mismatch,
  and (b) re-verify the subset immediately before compilation. (a) was **not** implemented
  in this run because the code was already frozen for the protocol hash.

## Mitigation applied

1. The single affected file was deleted and re-uploaded from the locally verified copy, then
   read eight times successfully.
2. All 60 run records were re-checked against the frozen audit before resuming: 0 mismatches.
3. The interrupted run was resumed only after that check.

## What was not established

The cause is not known: memory errors, a failing disk block, a filesystem/cache bug and
concurrent writes have not been distinguished. The server previously showed the same symptom
for large model files across two Python installations. **Do not treat the server as a trusted
bit-exact store**; verify hashes at every stage and keep independent local copies of every
input and artefact.
