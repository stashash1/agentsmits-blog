"""Allow `python -m agentsblog ...` invocations."""
from agentsblog.cli import main

if __name__ == "__main__":
    raise SystemExit(main())