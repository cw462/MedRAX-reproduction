"""CLI for the M5 v2 data and RSI preparation."""

import argparse
import json
from pathlib import Path

from .data import prepare
from .search import ARMS
from .workflow import MODEL_IDS, NEXT_PHASES, config_file, dry_run, execute_arm, freeze_all, preflight, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-data", "dry-run", "preflight", "bundle", *NEXT_PHASES, "freeze", "report"))
    parser.add_argument("--config", type=Path, default=Path("configs/m5_rsi.yaml"))
    parser.add_argument("--backbone", choices=tuple(MODEL_IDS))
    parser.add_argument("--arm", choices=tuple(ARMS))
    parser.add_argument("--output", type=Path, help="Staging destination for the bundle command")
    args = parser.parse_args()
    config = config_file(args.config)
    if args.backbone and args.backbone not in config["models"]:
        parser.error(f"backbone {args.backbone} is disabled in the active configuration")
    if args.command == "prepare-data":
        value = prepare(Path(config["project_root"]), Path(config["artifacts"]), Path(config["prior_eval"]),
                        seed=config["seed"], openi=Path(config["openi_archive"]))
    elif args.command == "bundle":
        from .stage import make_bundle

        value = make_bundle(config, output=args.output)
    elif args.command in NEXT_PHASES:
        if not args.backbone or (not args.arm and args.command != "smoke"):
            parser.error("execution needs --backbone and --arm; smoke needs only --backbone")
        value = execute_arm(config, args.command, args.backbone, args.arm or "DATA")
    else:
        commands = {"dry-run": dry_run, "preflight": preflight, "freeze": freeze_all, "report": report}
        value = commands[args.command](config)
    print(json.dumps(value, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
