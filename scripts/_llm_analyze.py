"""Compatibility entry for existing scheduled tasks; editorial logic lives in the package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentsblog.cli import main

if __name__ == '__main__':
    raise SystemExit(main(['analyze', *sys.argv[1:]]))
