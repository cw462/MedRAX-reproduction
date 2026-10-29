# The ledger fault of 2026-10-29 19:50, and what it actually was

At 19:50:46 the S2 run died with `LedgerIntegrityError: Ledger is closed or untrusted`.
This note records the evidence and the repair, because the first explanation ("someone
else wrote the ledger") is wrong and the real one matters for every later paid run.

## What the run saw

B arm, question `3686_8353801520174`, model call 2 of that question:

```
{"node":"money_reserve","model_ordinal":2,"reason":"integrity","status":"blocked",...}
```

`reserve()` calls `_check_disk()`, which compares the SHA-256 of the ledger file with the
hash the guard recorded after its own last commit. They differed, so the guard marked
itself poisoned and refused every later call. `reserve` raised, the question was
journalled as a monetary guard error, and the next `ledger_summary()` call crashed on the
poisoned guard. The run stopped at 38 completed questions.

## What was really happening

The file was **not** being written by a second process:

* no process had it open (`/proc/*/fd` scan), no crontab, no lock holder;
* its `mtime` never moved from 19:50:46, and its generation stayed 4507;
* but successive reads of the same path returned **two different byte streams**:

| read | sha256 (first 16) |
|---|---|
| 1 | `897378216cf2427b` |
| 6 | `e8656d73f25e78cc` |
| 7 | `897378216cf2427b` |

Both are 2,071,904 bytes, both parse as valid ledgers with generation 4507 and
`committed_cny` 77.124076, and both have 2,253 reservations. Their parsed states differ
only inside `reservations` — one settlement entry. In other words the same inode was
serving a pre-crash and a post-crash page for the same file, alternating.

So this is a **torn read at the filesystem/page-cache level on that inode**, not a
concurrent writer. The guard was right to refuse: had it continued, it would have
committed on top of one of two states with no way to know which one the next reader
would see.

Context worth keeping: the root filesystem was at 100% (`11G` free of 1.9T, ext4,
`errors=remount-ro`) when this happened. That may or may not be the trigger; it is the
one abnormal environmental fact.

## Repair

1. Captured both variants to `/tmp/ledger_variant_{1,2}.json`.
2. Took the variant that also matched the 19:59 `cp -p` backup and wrote it to a new
   inode (`cp` to `.new`, `mv` over the path), keeping the path and therefore the
   monetary-policy digest in the run manifests unchanged.
3. Verified 40 consecutive reads give one hash, and that a fresh `ProviderLedger` opens
   with `_disk_hash == sha256(file)` and reports `remaining 999922.88`.
4. Removed the failed question's `started`+`terminal` pair from `results.jsonl` (2 records,
   back up kept as `results.jsonl.bak-before-resume`) so it would run again.
5. Added `RESUME=1` support to `run_arm.sh` (the flag existed in the eval but was not
   exposed), then resumed with `--resume`.

The resumed run completed `3686_8353801520174` normally and continued from question 40.
The 38 questions already paid for were **not** re-run. Cost of the incident: one
question's worth of calls, roughly 0.15 CNY.

## Recurrence (20:26–20:30), and the operational fix

The rewrite fixed the file for idle reads but not the fault. A round 1 died the same
way at question 6 (`11858_8353800664572`, terminal status `monetary_guard_error`). The
pattern is now clear: **the file reads consistently while idle (60/60 identical hashes)
and tears only under a running arm**, after a few hundred commits.

Decision: do not weaken the guard's check. It is the component that stops the accounting
from being written onto an unknown state, and a retry there would trade that safety for
liveness on a filesystem that is already suspect.

Operational mitigation instead:

1. **A fresh ledger, `api_budget_qwen_100cny_v9.json`**, created with
   `inherit_ledger_path = v8` so the committed total (79.900292) carries over without
   recomputation. B's 38/60 is unaffected: scoring reads the run's `results.jsonl`, not
   the ledger.
2. **A supervisor around each arm** (`run_round1_v9.sh`): if the eval exits without
   `stop_reason == "complete"`, it drops the single `monetary_*` journal pair with
   `repair_journal.py` and resumes the same arm, up to eight attempts. Every real
   completion is kept; at most one question is lost per fault.
3. The half-finished A arm built against v8's monetary policy cannot resume on v9 (the
   policy digest is part of the plan hash), so it was set aside as
   `runs/v4_A_r1.pre-v9-*` and A restarted clean on v9.

Cost of the two faults so far: about two questions' worth of calls (≈0.3 CNY) plus the
five A questions that had to be restarted (≈0.6 CNY).

## Lessons for the next paid run

* `Ledger is closed or untrusted` does not imply a second writer; check whether the file
  reads consistently before blaming concurrency. A cheap 40-read hash loop settles it.
* Do not disable the guard to "get the run moving": with two possible states, continuing
  would silently corrupt the accounting.
* Keep `--resume` reachable from the arm launcher. Without it the only options were to
  re-pay for 39 questions or to hand-edit the journal.
* Free disk space before the next long run. 11G is enough for journals but leaves no room
  for a filesystem that is already behaving oddly.
