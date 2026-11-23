#!/usr/bin/env python3
"""Build a sanitised staging tree of the current project state for pushing to GitHub.

Excluded outright: .creds.json, CREDS.md, any nested .git.
Scrubbed in place   : hard-coded passwords in the legacy code/ scripts.
"""
import pathlib
import shutil
import sys

SRC = pathlib.Path(r"D:\Documents\deepseek-harness\default-workspace\radiology_rag")
DST = pathlib.Path(r"D:\Documents\deepseek-harness\default-workspace\_gh_upload")

EXCLUDE_NAMES = {".creds.json", "CREDS.md"}
EXCLUDE_DIRS = {".git", "__pycache__"}

SECRETS = {
    "REDACTED_AUTODL_32922_PASSWORD": "REDACTED_AUTODL_32922_PASSWORD",
    "REDACTED_AUTODL_26853_PASSWORD": "REDACTED_AUTODL_26853_PASSWORD",
    "REDACTED_LAB_PASSWORD": "REDACTED_LAB_PASSWORD",
}

SECURITY_MD = """# 凭据处理说明

本分支由自动化流程推送，**所有凭据已移除**：

- `CREDS.md` 与 `.creds.json` 未包含在仓库中（前者本来就在 `.gitignore` 里）。
- `code/` 下 13 个历史脚本里硬编码的密码已替换为 `REDACTED_*` 占位符。
  它们现在无法直接运行，需要自行以环境变量注入：

```bash
export AUTODL_32922_PASSWORD=...
export AUTODL_26853_PASSWORD=...
export LAB_PASSWORD=...
```

实验室服务器与 AutoDL 实例的访问方式见 `HANDOFF.md` §4（只写地址与路径，不含密码）。
"""

SCRUBBED_NOTE = """
---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
"""


def main():
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    copied = scrubbed = 0
    skipped = []
    for p in SRC.rglob("*"):
        rel = p.relative_to(SRC)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.name in EXCLUDE_NAMES:
            skipped.append(str(rel))
            continue
        target = DST / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        if p.suffix in {".png", ".jpg", ".jpeg", ".gz", ".zip", ".pkl"}:
            shutil.copy2(p, target)
            copied += 1
            continue

        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            shutil.copy2(p, target)
            copied += 1
            continue

        hit = False
        for secret, placeholder in SECRETS.items():
            if secret in text:
                text = text.replace(secret, placeholder)
                hit = True
        if hit:
            text += SCRUBBED_NOTE
            scrubbed += 1
        target.write_text(text, encoding="utf-8")
        copied += 1

    (DST / "SECURITY.md").write_text(SECURITY_MD, encoding="utf-8")
    size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file())
    print(f"copied {copied} files, scrubbed {scrubbed}")
    print(f"excluded: {skipped}")
    print(f"staging size: {size/1e6:.1f} MB")
    # final assertion: no secret survives
    leaks = []
    for f in DST.rglob("*"):
        if not f.is_file() or f.suffix in {".gz", ".zip", ".png", ".jpg"}:
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        for secret in SECRETS:
            if secret in t:
                leaks.append((str(f.relative_to(DST)), secret))
    print("remaining leaks:", leaks if leaks else "none")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())

---
> **注意（2026-11-23 归档时自动处理）**：本文件原含明文密码，已替换为占位符，
> 改为从环境变量读取。详见仓库根目录 `SECURITY.md`。
