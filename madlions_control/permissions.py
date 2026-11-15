"""Small helpers for the permission-fix flow.

Kept separate from the GTK window so the command construction and temporary
rule handling can be tested without a display.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

FIX_SCRIPT = (
    'install -Dm644 "$1" /etc/udev/rules.d/71-madlions.rules && '
    "udevadm control --reload-rules && "
    "udevadm trigger --subsystem-match=hidraw"
)


def fix_command(rule_path: Path) -> list[str]:
    """Return the exact argument list passed to pkexec."""
    return ["pkexec", "sh", "-c", FIX_SCRIPT, "sh", str(rule_path)]


def stage_rule(rule_text: str) -> tuple[Path, Path]:
    """Write *rule_text* to a private temp file for pkexec.

    Returns ``(temp_dir, rule_path)``; the caller owns cleanup.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="madlions-rule-"))
    rule_path = temp_dir / "71-madlions.rules"
    try:
        rule_path.write_text(rule_text, encoding="utf-8")
        rule_path.chmod(0o644)
    except OSError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return temp_dir, rule_path
