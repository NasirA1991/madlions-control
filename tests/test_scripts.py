"""Installer and uninstaller command-line contracts."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install.sh"
UNINSTALL = ROOT / "uninstall.sh"


def run_script(
    script: Path,
    *args: str,
    env: dict[str, str] | None = None,
    umask: int | None = None,
    root: bool = False,
) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    command = [str(script), *args]
    if root and os.geteuid() != 0:
        unshare = shutil.which("unshare")
        if unshare is None:
            raise unittest.SkipTest("unshare is required to exercise root-only paths")
        command = [unshare, "-r", "--", *command]
    return subprocess.run(
        command,
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
        preexec_fn=(lambda: os.umask(umask)) if umask is not None else None,
    )


def write_package_manager(bindir: Path, name: str) -> None:
    """Write a tiny manager stub that claims to own the queried path."""
    script = bindir / name
    if name == "pacman":
        body = "echo madlions-control\n"
    elif name == "dpkg":
        body = 'echo "madlions-control: $2"\n'
    elif name == "rpm":
        body = "echo madlions-control-0.3.3-1.x86_64\n"
    else:
        raise ValueError(name)
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(0o755)


class InstallerCliTests(unittest.TestCase):
    def test_install_help_lists_modes(self):
        result = run_script(INSTALL, "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("--udev-only", result.stdout)
        self.assertIn("--user", result.stdout)
        self.assertIn("--skip-deps", result.stdout)

    def test_uninstall_help_lists_modes(self):
        result = run_script(UNINSTALL, "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("--user", result.stdout)
        self.assertIn("--udev-only", result.stdout)
        self.assertIn("/etc/udev/rules.d/71-madlions.rules", result.stdout)
        self.assertIn("/usr/lib/udev/rules.d/71-madlions.rules", result.stdout)

    def test_unknown_option_is_rejected(self):
        result = run_script(INSTALL, "--not-an-option")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)
        result = run_script(UNINSTALL, "--not-an-option")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root is not rejected in this environment")
    def test_system_modes_require_root(self):
        install = run_script(INSTALL)
        self.assertEqual(install.returncode, 1)
        self.assertIn("system install requires root", install.stderr)
        udev = run_script(INSTALL, "--udev-only")
        self.assertEqual(udev.returncode, 1)
        self.assertIn("--udev-only requires root", udev.stderr)
        uninstall = run_script(UNINSTALL)
        self.assertEqual(uninstall.returncode, 1)
        self.assertIn("system uninstall requires root", uninstall.stderr)
        uninstall_udev = run_script(UNINSTALL, "--udev-only")
        self.assertEqual(uninstall_udev.returncode, 1)
        self.assertIn("--udev-only requires root", uninstall_udev.stderr)

    def test_missing_python_reports_dependency_help(self):
        with tempfile.TemporaryDirectory() as temp:
            bindir = Path(temp) / "bin"
            bindir.mkdir()
            for name in ("bash", "dirname"):
                target = shutil.which(name)
                if target:
                    (bindir / name).symlink_to(target)
            env = {"PATH": str(bindir), "HOME": temp}
            result = run_script(INSTALL, "--user", env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Missing Python 3", result.stderr)
            self.assertIn("Install the build/runtime dependencies", result.stderr)

    def test_user_install_mentions_udev_only(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {"HOME": temp, "XDG_DATA_HOME": str(Path(temp) / "data")}
            result = run_script(INSTALL, "--user", "--skip-deps", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("sudo ./install.sh --udev-only", result.stdout)
            self.assertTrue((Path(temp) / ".local/bin/madlions-control").is_file())

    def test_staged_install_writes_prefix_rule_not_etc(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {"DESTDIR": temp, "PREFIX": "/usr"}
            result = run_script(INSTALL, "--skip-deps", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(temp)
            self.assertTrue((root / "usr/lib/udev/rules.d/71-madlions.rules").is_file())
            self.assertFalse((root / "etc/udev/rules.d/71-madlions.rules").exists())
            self.assertTrue((root / "usr/bin/madlions-control").is_file())
            self.assertTrue((root / "usr/bin/madlionsctl").is_file())
            self.assertTrue((root / "usr/lib/madlions-control/data/udev/71-madlions.rules").is_file())
            self.assertEqual(
                (root / "usr/lib/madlions-control/madlions_control/__init__.py").stat().st_mode & 0o777,
                0o644,
            )

    def test_install_rejects_udev_only_with_user_or_destdir(self):
        with tempfile.TemporaryDirectory() as temp:
            for args, env in (
                (["--udev-only", "--user"], {}),
                (["--udev-only"], {"DESTDIR": temp}),
            ):
                result = run_script(INSTALL, *args, env=env)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be used together" if "--user" in args else "does not support DESTDIR", result.stderr)

    def test_install_sets_readable_permissions_under_restrictive_umask(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {"DESTDIR": temp, "PREFIX": "/usr"}
            result = run_script(INSTALL, "--skip-deps", env=env, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = Path(temp)
            self.assertEqual(
                (root / "usr/lib/madlions-control/madlions_control/__init__.py").stat().st_mode & 0o777,
                0o644,
            )
            self.assertEqual(
                (root / "usr/lib/madlions-control/madlions_control").stat().st_mode & 0o777,
                0o755,
            )

    def test_install_user_does_not_create_etc_rule(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {"HOME": temp, "XDG_DATA_HOME": str(Path(temp) / "data")}
            result = run_script(INSTALL, "--user", "--skip-deps", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((Path(temp) / "etc/udev/rules.d/71-madlions.rules").exists())


class UninstallStagingTests(unittest.TestCase):
    def test_system_removes_prefix_and_etc_rule_but_not_atk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            etc_rule = root / "etc/udev/rules.d/71-madlions.rules"
            prefix_rule = root / "usr/lib/udev/rules.d/71-madlions.rules"
            atk_rule = root / "etc/udev/rules.d/71-atk-control.rules"
            lib_marker = root / "usr/lib/madlions-control/marker"
            for path in (etc_rule, prefix_rule, atk_rule, lib_marker):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test\n", encoding="utf-8")

            env = {"DESTDIR": temp, "PREFIX": "/usr"}
            result = run_script(UNINSTALL, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(etc_rule.exists())
            self.assertFalse(prefix_rule.exists())
            self.assertTrue(atk_rule.exists())
            self.assertFalse(lib_marker.exists())

    def test_user_uninstall_never_removes_staged_etc_rule(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            stage = root / "stage"
            etc_rule = stage / "etc/udev/rules.d/71-madlions.rules"
            prefix_rule = stage / home.relative_to(home.anchor) / ".local/lib/udev/rules.d/71-madlions.rules"
            for path in (etc_rule, prefix_rule):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test\n", encoding="utf-8")
            env = {"HOME": str(home), "DESTDIR": str(stage)}
            result = run_script(UNINSTALL, "--user", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(etc_rule.exists())
            self.assertFalse(prefix_rule.exists())

    def test_uninstall_udev_only_rejects_user_and_destdir(self):
        with tempfile.TemporaryDirectory() as temp:
            for args, env in (
                (["--udev-only", "--user"], {}),
                (["--udev-only"], {"DESTDIR": temp}),
            ):
                result = run_script(UNINSTALL, *args, env=env)
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be used together" if "--user" in args else "does not support DESTDIR", result.stderr)


class PackageGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() != 0:
            if shutil.which("unshare") is None:
                raise unittest.SkipTest("unshare is required to exercise root-only paths")
            probe = subprocess.run(
                ["unshare", "-r", "true"],
                capture_output=True,
                text=True,
                check=False,
            )
            if probe.returncode != 0:
                raise unittest.SkipTest("user namespaces are unavailable")

    def _env(self, temp: str, manager: str) -> dict[str, str]:
        bindir = Path(temp) / "bin"
        bindir.mkdir()
        write_package_manager(bindir, manager)
        return {
            "HOME": temp,
            "PREFIX": str(Path(temp) / "prefix"),
            "PATH": f"{bindir}:{os.environ['PATH']}",
        }

    def test_package_owned_install_is_refused_for_each_manager(self):
        for manager in ("pacman", "dpkg", "rpm"):
            with self.subTest(manager=manager), tempfile.TemporaryDirectory() as temp:
                env = self._env(temp, manager)
                result = run_script(INSTALL, "--skip-deps", env=env, root=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("is owned by package madlions-control", result.stderr)
                self.assertIn("--force", result.stderr)
                self.assertFalse((Path(temp) / "prefix/lib/madlions-control").exists())

    def test_force_install_bypasses_package_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            env = self._env(temp, "pacman")
            result = run_script(INSTALL, "--skip-deps", "--force", env=env, root=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            prefix = Path(temp) / "prefix"
            self.assertTrue((prefix / "lib/madlions-control/madlions_control/__init__.py").is_file())
            self.assertTrue((prefix / "bin/madlions-control").is_file())

    def test_destdir_skips_package_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            bindir = Path(temp) / "bin"
            bindir.mkdir()
            write_package_manager(bindir, "pacman")
            env = {
                "DESTDIR": temp,
                "PREFIX": "/usr",
                "PATH": f"{bindir}:{os.environ['PATH']}",
            }
            result = run_script(INSTALL, "--skip-deps", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse("is owned by package" in result.stderr)
            self.assertTrue((Path(temp) / "usr/lib/udev/rules.d/71-madlions.rules").is_file())

    def test_package_owned_uninstall_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            env = self._env(temp, "pacman")
            marker = Path(temp) / "prefix/lib/madlions-control/marker"
            marker.parent.mkdir(parents=True)
            marker.write_text("keep\n", encoding="utf-8")
            result = run_script(UNINSTALL, env=env, root=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("is owned by package madlions-control", result.stderr)
            self.assertTrue(marker.is_file())

    def test_icon_cache_is_only_refreshed_when_it_exists(self):
        for with_cache in (True, False):
            with self.subTest(with_cache=with_cache), tempfile.TemporaryDirectory() as temp:
                bindir = Path(temp) / "bin"
                bindir.mkdir()
                stub = bindir / "gtk-update-icon-cache"
                stub.write_text('#!/bin/sh\nprintf ran > "$HOME/icon-cache-ran"\n', encoding="utf-8")
                stub.chmod(0o755)
                home = Path(temp) / "home"
                icondir = home / ".local/share/icons/hicolor"
                icondir.mkdir(parents=True)
                if with_cache:
                    (icondir / "icon-theme.cache").write_text("cache\n", encoding="utf-8")
                env = {
                    "HOME": str(home),
                    "PATH": f"{bindir}:{os.environ['PATH']}",
                }
                result = run_script(INSTALL, "--user", "--skip-deps", env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((home / "icon-cache-ran").exists(), with_cache)


if __name__ == "__main__":
    unittest.main()
