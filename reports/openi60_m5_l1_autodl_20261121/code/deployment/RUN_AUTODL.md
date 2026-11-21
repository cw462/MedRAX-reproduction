# OpenI60 on AutoDL

Working directory: `/root/autodl-tmp/openi60_m5_l1_20261121`.

The existing environment, weights and six resident GPU model processes are reused.
The 11-tool menu, sampling parameters and memory-writer route match the original
M5 configuration. B0 and L1 use separate prediction, feedback and memory storage.

```bash
cd /root/autodl-tmp/openi60_m5_l1_20261121
/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python -m unittest discover -s tests -v
/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python -B openi60_cli.py preflight --work runs/openi60_s20261121_fast
```

The native resident dispatcher serves the original image-tool implementations.
CPU ROI processing, retrieval, reflection, Verify and M5 memory retain their
native implementations. Resident model weights are shared; tool results and
mutable memory remain inside each arm's output directory.

Execution uses `OPENI60_MAIN_API_KEY` and `OPENI60_MEMORY_API_KEY` populated from
the existing Token Plan credential, then runs:

```bash
/root/autodl-tmp/medrax_r55_top4_full848/env/modern/bin/python -B -u -m openi60.parallel --work runs/openi60_s20261121_fast --execute
```

B0 and L1 execute concurrently. Each arm preserves its question order and feedback
updates. GPU requests use the existing resident pool's shared execution lock.

Status and final paired results are under `runs/openi60_s20261121_fast`.
