"""Register the fixtures playbook/lens library so the loader tests have data."""
from pathlib import Path

from novahos.playbooks import loader

_FIX = Path(__file__).parent / "fixtures"
loader.reset()
loader.register_dirs(_FIX / "playbooks", _FIX / "lenses")
