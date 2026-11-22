"""Stage the frozen R55 inputs and memory runner for the AutoDL comparison."""

from copy import deepcopy
import json
from pathlib import Path


TOOLS = (
    "chest_xray_expert", "llava_med_qa", "medgemma", "llava_rad", "medvlm_r1",
    "maira2_grounded_report", "xray_phrase_grounding", "roi_crop",
)
MODELS = {"flash": "qwen3.6-flash", "plus": "qwen3.7-plus", "deepseek": "deepseek-flash"}
BASELINES = ("ReAct", "CRITIC", "Reflexion")
WRITER = {
    "endpoint": "https://api.deepseek.com/chat/completions",
    "model_requested": "deepseek-flash",
    "transport": "deepseek_official",
    "enable_thinking": False,
}
SHARED_MODULES = (
    "r55_autodl_memory_recovery_official.py",
    "r55_deepseek_official.py",
    "r55_memevolve_driver_official.py",
    "reference_model_fixture.py",
    "run_r55_full848_dataset.py",
    "score_r55_full848_dataset.py",
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _link(destination, source):
    source.resolve(strict=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() and not destination.is_symlink():
        destination.symlink_to(source, target_is_directory=source.is_dir())
    if destination.resolve(strict=True) != source.resolve():
        raise ValueError(f"Unexpected donor for {destination}")


def _replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unexpected memory runner source around {old!r}")
    return source.replace(old, new, 1)


def _runner(source):
    source = _replace(
        source,
        "    from r55_qwen8_runtime import TOOLS",
        f"    TOOLS = {TOOLS!r}",
    )
    source = _replace(
        source,
        "                from r55_qwen8_runtime import wait_for_case\n"
        "                wait_for_case()",
        "                from r55_deepseek_rerun_runtime import wait_for_arm\n"
        "                wait_for_arm(root.parent, os.environ['R55_QWEN8_ARM'])",
    )
    source = _replace(
        source,
        "        assert service.paid.route['transport'] == 'token_plan'",
        "        if manifest['protocol']['model'] == DEEPSEEK_MODEL:\n"
        "            assert manifest['config']['profile']['credential_slot'] == 'deepseek_official'\n"
        "            assert str(service.paid.client.base_url).rstrip('/') == 'https://api.deepseek.com'\n"
        "        else:\n"
        "            assert service.paid.route['transport'] == 'token_plan'",
    )
    return _replace(
        source,
        "    if args.phase == 'run':",
        "    if args.phase == 'run' and args.dataset:\n"
        "        args.phase = 'dataset'\n"
        "    if args.phase == 'run':",
    )


def _manifest(root, prior8, official, variant, arm, dataset, count):
    prior = prior8 / ("flash" if variant == "deepseek" else variant)
    donor_arm = arm if arm in ("M2", "M5") else "ReAct"
    manifest = _read(prior / "manifests" / donor_arm / f"{dataset}.json")
    model = MODELS[variant]
    if variant == "deepseek":
        rel = Path("manifests") / donor_arm / f"{dataset}.json"
        profile_path = official / rel
        if not profile_path.is_file():
            profile_path = official.with_name("r55_autodl_deepseek41_main_20261115_001") / rel
        profile_donor = _read(profile_path)
        for field in ("inputs", "order", "reference_files"):
            if manifest[field] != profile_donor[field]:
                raise ValueError(f"DeepSeek input mismatch for {arm}/{dataset}: {field}")
        manifest["config"].update(
            {key: deepcopy(profile_donor["config"][key])
             for key in ("model", "profile", "credential_slot", "extra_body")}
        )
        manifest["protocol"].update(model=model, enable_thinking=False)
    if (manifest["config"]["model"], manifest["protocol"]["model"]) != (model, model):
        raise ValueError(f"Incorrect model for {variant}/{arm}/{dataset}")
    runtime = manifest["runtime"]
    if (tuple(runtime["arms"]["M"]["tools"]) != TOOLS
            or set(runtime["tools"]) != set(TOOLS)
            or len(manifest["inputs"]) != count):
        raise ValueError(f"Incorrect eight-tool protocol for {variant}/{arm}/{dataset}")
    if manifest["skill_enabled"]:
        raise ValueError(f"Unexpected skill policy for {variant}/{arm}/{dataset}")
    ident = f"{root.name}-{variant}-{arm}-{dataset}"
    manifest["config"]["experiment_id"] = manifest["protocol"]["experiment_id"] = ident
    manifest["arm"] = f"R55-{arm}"
    manifest["implementation_revision"] = "R55-eight-tools"
    manifest["deepseek"] = WRITER if arm in ("M2", "M5") else None
    return manifest


def stage(root: Path, prior8: Path, official: Path, datasets: dict):
    """Bind the existing data and environment and write separate manifests."""
    shared = root / "bin"
    shared.mkdir(parents=True, exist_ok=True)
    for name in SHARED_MODULES:
        _link(shared / name, prior8 / "bin" / name)
    runner_path = shared / "run_qwen8_memory.py"
    runner = _runner((prior8 / "bin" / runner_path.name).read_text(encoding="utf-8"))
    compile(runner, str(runner_path), "exec")
    runner_path.write_text(runner, encoding="utf-8")

    for variant in MODELS:
        model_root = root / variant
        donor = prior8 / ("flash" if variant == "deepseek" else variant)
        for directory in ("env", "data", "refs", "runtime"):
            _link(model_root / directory, donor / directory)
        _link(model_root / "bin", shared)
        for source in (donor / "code/experiments").iterdir():
            if source.name in ("__pycache__", "r55_resident_tools.py"):
                continue
            _link(model_root / "code/experiments" / source.name, source)
        # Keep the resident routing module local so the batch can bind the active workers.
        resident = model_root / "code/experiments/r55_resident_tools.py"
        if not resident.exists():
            resident.write_text((donor / "code/experiments" / resident.name).read_text(
                encoding="utf-8"), encoding="utf-8")

        methods = (*BASELINES, "M2", "M5") if variant == "deepseek" else (*BASELINES, "M2")
        for arm in methods:
            for dataset, count in datasets.items():
                manifest = _manifest(root, prior8, official, variant, arm, dataset, count)
                path = model_root / "manifests" / arm / f"{dataset}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        plan = {
            "arms": dict.fromkeys(methods, MODELS[variant]),
            "deepseek_by_arm": {arm: WRITER for arm in methods if arm in ("M2", "M5")},
            "tool_count": len(TOOLS),
            "datasets": datasets,
        }
        (model_root / "plan.json").write_text(json.dumps(plan, indent=2) + "\n",
                                             encoding="utf-8")
