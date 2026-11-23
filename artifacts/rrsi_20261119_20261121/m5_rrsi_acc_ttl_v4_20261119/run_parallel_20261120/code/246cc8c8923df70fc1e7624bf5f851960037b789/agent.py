"""Editable entrypoints for native M5 inference and post-prediction memory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m5_native.agent import initialize, predict, observe, migrate
