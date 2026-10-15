import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SystemBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mod-desktop-system-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / "build-system"
        self.module = load("system_build", ROOT / "utils/linux/system-build.py")
        self.module.ROOT = self.root
        self.module.MOD_UI = self.root / "external-mod-ui"

    def write(self, path, text="fixture"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_isolated_sources_exclude_bundled_outputs(self):
        source = self.root / "src/systray"
        self.write(source / "main.cpp")
        for name in ("main.cpp.o", "mod-desktop", "qrc_mod-desktop.hpp", "old.so"):
            self.write(source / name)
        self.write(self.root / "VERSION", "0.0.1")
        (self.root / "res").mkdir()
        self.module.COMPONENTS = {"system-launcher": (source, "systray")}
        self.module.prepare(self.build, "system-launcher")
        copied = self.build / "src/systray"
        self.assertEqual([p.name for p in copied.iterdir()], ["main.cpp"])
        self.assertEqual((self.build / "VERSION").read_text(), "0.0.1")
        self.assertTrue((source / "main.cpp.o").exists())

    def test_stage_uses_external_ui_without_bundling_system_libraries(self):
        for name in ("src/systray/mod-desktop", "src/mod-host/mod-host",
                     "midi/mod-midi-merger-standalone", "midi/mod-midi-broadcaster-standalone",
                     "src/mod-utils/libmod_utils.so"):
            self.write(self.build / name)
        for name in ("mod/__init__.py", "modtools/__init__.py", "html/index.html",
                     "default.pedalboard/manifest.ttl"):
            self.write(self.module.MOD_UI / name)
        self.write(self.root / "pedalboards/example")
        self.write(self.root / "utils/linux/mod-hardware-descriptor.json")
        for name in ("utils/linux/system-host.py", "utils/cxfreeze/mod-ui-setup.py",
                     "utils/cxfreeze/mod-pedalboard-setup.py"):
            self.write(self.root / name)
        self.module.stage(self.build, sys.executable)
        self.assertEqual((self.build / "mod").resolve(), (self.module.MOD_UI / "mod").resolve())
        self.assertTrue((self.build / "lib/libmod_utils.so").exists())
        self.assertFalse((self.build / "mod-desktop").is_symlink())
        self.assertFalse((self.build / "jackd").exists())
        self.assertFalse((self.build / "libjack.so.0").exists())
        self.assertFalse((self.build / "lib/library.zip").exists())
        self.assertIn(shlex.quote(sys.executable), (self.build / "mod-ui").read_text())
        self.module.stage(self.build, sys.executable)

    def test_stage_missing_binary_is_an_error(self):
        self.build.mkdir()
        with self.assertRaisesRegex(RuntimeError, "Missing system build input"):
            self.module.stage(self.build, sys.executable)

    def test_system_graph_does_not_load_pawpaw_or_plugin_builder(self):
        result = subprocess.run(
            ["make", "-n", "SYSTEM_DEPS=1", "CC=echo x86_64-linux-gnu", "MAKE=echo"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stderr, "")
        self.assertIn("system-build.py prepare", result.stdout)
        self.assertIn("MOD_DESKTOP=0 mod-host", result.stdout)
        self.assertIn("mod-midi-merger-standalone", result.stdout)
        self.assertNotIn("PawPaw", result.stdout)
        self.assertNotIn("plugin-builder", result.stdout)
        self.assertNotIn("cxfreeze", result.stdout)

    def test_user_flags_do_not_replace_required_component_flags(self):
        self.write(self.root / "Makefile", "include utils/linux/system.mk\n")
        self.write(self.root / "utils/linux/system.mk",
                   (ROOT / "utils/linux/system.mk").read_text())
        self.write(self.root / "utils/linux/system-build.py",
                   (ROOT / "utils/linux/system-build.py").read_text())
        self.write(self.root / "src/systray/Makefile",
                   'CXXFLAGS += -DREQUIRED\nall:\n\t@echo "flags: $(CXXFLAGS)"\n')
        self.write(self.root / "VERSION", "0.0.1")
        (self.root / "res").mkdir()
        cmake = self.write(self.root / "bin/cmake", "#!/bin/sh\nexit 0\n")
        cmake.chmod(0o755)
        result = subprocess.run(
            ["make", "SYSTEM_DEPS=1", "CC=echo x86_64-linux-gnu", "PKG_CONFIG=true",
             f"PYTHON={sys.executable}", "CXXFLAGS=-DUSER", "system-launcher"],
            cwd=self.root, text=True, capture_output=True, check=True,
            env={**os.environ, "PATH": str(cmake.parent) + os.pathsep + os.environ["PATH"]},
        )
        self.assertIn("flags: -DUSER -DREQUIRED", result.stdout)


class SystemHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mod-desktop-host-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = ROOT / "utils/linux/system-host.py"

    def client(self, name, fail=False):
        path = self.root / name
        path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(f"""\
            import os
            from pathlib import Path
            import signal
            import time
            root = Path(__file__).parent
            (root / '{name}.pid').write_text(str(os.getpid()))
            if {fail!r}:
                raise SystemExit(3)
            (root / '{name}.ready').touch()
            if '{name}' == 'mod-host-native':
                assert all((root / (n + '.ready')).exists()
                           for n in ('mod-midi-merger', 'mod-midi-broadcaster'))
                print('mod-host ', end='', flush=True)
                time.sleep(0.02)
                print('ready!', flush=True)
                time.sleep(0.1)
                os.kill(os.getppid(), signal.SIGTERM)
            while True:
                time.sleep(1)
        """))
        path.chmod(0o755)

    def run_host(self):
        runner = self.root / "runner.py"
        runner.write_text(textwrap.dedent(f"""\
            import importlib.util
            from pathlib import Path
            spec = importlib.util.spec_from_file_location('system_host', {str(self.host)!r})
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            root = Path(__file__).parent
            module.__file__ = str(root / 'system-host.py')
            class Jack:
                def jack_port_by_name(self, client, name):
                    files = {{b'mod-midi-merger:out': 'mod-midi-merger',
                              b'mod-midi-broadcaster:in': 'mod-midi-broadcaster'}}
                    return name in files and (root / (files[name] + '.ready')).exists()
                def jack_client_close(self, client):
                    (root / 'jack-closed').touch()
            module.open_jack = lambda: (Jack(), 1)
            raise SystemExit(module.main())
        """))
        with subprocess.Popen([sys.executable, str(runner)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.communicate(timeout=2)
                self.fail("system host did not finish")
        self.assertTrue((self.root / "jack-closed").exists())
        for pidfile in self.root.glob("*.pid"):
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)
        return process.returncode, stdout, stderr

    def test_waits_for_midi_ports_and_cleans_up_on_stop(self):
        for name in ("mod-midi-merger", "mod-midi-broadcaster", "mod-host-native"):
            self.client(name)
        code, stdout, stderr = self.run_host()
        self.assertEqual(code, 0, stderr)
        self.assertIn(b"mod-host ready!", stdout)

    def test_child_failure_is_reported_and_other_children_are_stopped(self):
        self.client("mod-midi-merger", fail=True)
        self.client("mod-midi-broadcaster")
        self.client("mod-host-native")
        code, _, stderr = self.run_host()
        self.assertEqual(code, 1)
        self.assertIn(b"exited with status 3", stderr)
        self.assertFalse((self.root / "mod-host-native.pid").exists())

    def test_missing_executable_is_reported(self):
        code, _, stderr = self.run_host()
        self.assertEqual(code, 1)
        self.assertIn(b"MOD Desktop system audio error", stderr)

    def test_invalid_port_is_reported(self):
        module = load("system_host", self.host)
        with patch.dict(os.environ, {"MOD_DEVICE_HOST_PORT": "invalid"}), \
                patch.object(module.signal, "signal"), \
                patch.object(module, "open_jack") as jack:
            with patch("sys.stderr"):
                self.assertEqual(module.main(), 1)
            jack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
