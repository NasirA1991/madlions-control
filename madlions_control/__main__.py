"""``python -m madlions_control`` — GUI by default, CLI for known commands."""

from __future__ import annotations

import sys

CLI_COMMANDS = {
    "status", "scan", "actuation", "rt", "light", "deadband", "features",
    "profile", "report", "test",
}


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] in CLI_COMMANDS:
        from .cli import main as cli_main

        return cli_main(argv)
    from .app import main as app_main

    return app_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
