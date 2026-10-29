"""stdin/stdout JSONL server for MAIRA-2 grounding (run with .venv-maira).

One model load, many calls. The client (main Agent environment) speaks one JSON
object per line and never imports torch/transformers for this tool.

Protocol
  -> {"cmd": "describe"}
  <- {"ok": true, "tool_version": ..., "model_dtype": ..., "vram_gib": ...}
  -> {"cmd": "ground", "image_path": "...", "phrase": "...", "max_new_tokens": 300}
  <- {"ok": true, "result": {...}}   or   {"ok": false, "error": "..."}
  -> {"cmd": "shutdown"}

Only framed JSON reaches stdout; library noise is redirected to stderr so the
client can never parse a partial model log as a result.
"""

import json
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    sys.path.insert(0, HERE)
    repo = os.environ["MEDRAX_REPO"]
    real_stdout = sys.stdout
    log = open(os.environ.get("MAIRA_WORKER_LOG", os.devnull), "a", encoding="utf-8")

    def emit(value):
        real_stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
        real_stdout.flush()

    grounding = None
    with redirect_stdout(log), redirect_stderr(log):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as error:
                emit({"ok": False, "error": f"bad request: {error}"})
                continue
            cmd = request.get("cmd")
            if cmd == "shutdown":
                emit({"ok": True})
                break
            try:
                if cmd == "load":
                    from maira_grounding import MairaGrounding
                    import torch
                    grounding = MairaGrounding(
                        source_path=os.path.join(repo, "medrax/tools/grounding.py"),
                        model_path=request["model_path"],
                        cache_dir=request.get("cache_dir"),
                        temp_dir=request.get("temp_dir"),
                        device=request.get("device", "cuda"))
                    emit({"ok": True, "tool_version": grounding.TOOL_VERSION,
                          "model_dtype": str(next(grounding.tool.model.parameters()).dtype),
                          "vram_gib": round(torch.cuda.memory_allocated() / 2 ** 30, 2)})
                elif cmd == "ground":
                    if grounding is None:
                        raise RuntimeError("worker has no model loaded")
                    emit({"ok": True, "result": grounding.ground(
                        request["image_path"], request["phrase"],
                        int(request.get("max_new_tokens", 300)))})
                elif cmd == "describe":
                    emit({"ok": True, "loaded": grounding is not None})
                else:
                    emit({"ok": False, "error": f"unknown cmd {cmd!r}"})
            except Exception as error:  # keep the worker alive for the next call
                emit({"ok": False, "error": f"{type(error).__name__}: {error}",
                      "traceback": traceback.format_exc()[-1200:]})
    log.close()


if __name__ == "__main__":
    main()
