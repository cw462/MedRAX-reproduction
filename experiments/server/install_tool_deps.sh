#!/bin/bash
# Install the extra Python packages the seven-tool registry needs.
# Falls back to local wheels when pip has no network (the lab server often cannot reach PyPI).
set +e
R=/home/imss/cw/MedRAX_reproduction_20261027
cd "$R"
echo "== base install"
"$R/.venv/bin/pip" install -q "transformers==4.45.2" "diffusers==0.31.0" pydicom accelerate 2>&1 | tail -3
echo "== local wheels (albumentations + qudida)"
for whl in "$R"/code/albumentations-1.3.1-py3-none-any.whl "$R"/code/qudida-0.0.4-py3-none-any.whl; do
  [ -f "$whl" ] && "$R/.venv/bin/pip" install -q --no-index --no-deps "$whl"
done
"$R/.venv/bin/python" - <<'PY'
for package in ("transformers", "diffusers", "albumentations", "qudida", "pydicom", "accelerate"):
    try:
        module = __import__(package)
        print(package, getattr(module, "__version__", "ok"))
    except Exception as exc:  # noqa: BLE001
        print(package, "MISSING", type(exc).__name__)
PY
