#!/usr/bin/env python3

import os
from pathlib import Path
import shlex
import shutil
import sys


ROOT = Path(__file__).resolve().parents[2]
MOD_UI = Path(os.environ.get("MOD_UI_DIR", ROOT / "src/mod-ui")).resolve()
COMPONENTS = {
    "system-host": (ROOT / "src/mod-host", "mod-host"),
    "system-utils": (MOD_UI / "utils", "mod-utils"),
    "system-launcher": (ROOT / "src/systray", "systray"),
}


def link(source, destination):
    if destination.is_symlink():
        destination.unlink()
    destination.symlink_to(source)


def check_python():
    sys.path.insert(0, str(MOD_UI))
    import mod
    from tornado import gen, util, web

    if not all((hasattr(gen, "Task"), hasattr(gen, "engine"),
                hasattr(util, "unicode_type"), hasattr(web, "asynchronous"))):
        raise RuntimeError(
            f"{MOD_UI} does not support the installed Tornado. "
            "Set MOD_UI_DIR to a compatible mod-ui checkout."
        )


def prepare(build, component):
    source, name = COMPONENTS[component]
    destination = build / "src" / name
    # Never reuse objects produced with PawPaw's compiler or static libraries.
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        ".git", "*.o", "*.so", "*.dll", "*.exe", "mod-host", "mod-desktop",
        "info.h", "qrc_*.hpp", "ui_*.hpp",
    ))
    if component == "system-launcher":
        link(ROOT / "VERSION", build / "VERSION")
        link(ROOT / "res", build / "res")


def stage(build, python):
    executable = shutil.which(python)
    if executable is None:
        raise RuntimeError(f"Python interpreter not found: {python}")
    (build / "lib").mkdir(exist_ok=True)
    for name, source in {
        "mod-desktop": build / "src/systray/mod-desktop",
        "mod-host-native": build / "src/mod-host/mod-host",
        "mod-midi-merger": build / "midi/mod-midi-merger-standalone",
        "mod-midi-broadcaster": build / "midi/mod-midi-broadcaster-standalone",
        "lib/libmod_utils.so": build / "src/mod-utils/libmod_utils.so",
        "mod": MOD_UI / "mod",
        "modtools": MOD_UI / "modtools",
        "html": MOD_UI / "html",
        "default.pedalboard": MOD_UI / "default.pedalboard",
        "pedalboards": ROOT / "pedalboards",
        "mod-hardware-descriptor.json": ROOT / "utils/linux/mod-hardware-descriptor.json",
    }.items():
        if not source.exists():
            raise RuntimeError(f"Missing system build input: {source}")
        if name == "mod-desktop":
            # initEvironment uses dladdr: the launcher must live in the runtime directory.
            shutil.copy2(source, build / name)
        else:
            link(source, build / name)
    for name, source in {
        "mod-host": ROOT / "utils/linux/system-host.py",
        "mod-ui": ROOT / "utils/cxfreeze/mod-ui-setup.py",
        "mod-pedalboard": ROOT / "utils/cxfreeze/mod-pedalboard-setup.py",
    }.items():
        script = build / f"{name}.py"
        shutil.copy2(source, script)
        wrapper = build / name
        wrapper.write_text(
            '#!/bin/sh\n'
            'cd -- "$(dirname -- "$0")" || exit 1\n'
            f'exec {shlex.quote(executable)} ./{name}.py "$@"\n'
        )
        wrapper.chmod(0o755)


def main():
    action, directory, *args = sys.argv[1:]
    build = Path(directory).absolute()
    if build != ROOT / "build-system":
        raise ValueError("The system build directory must be <repository>/build-system")
    if build.is_symlink():
        raise ValueError("The system build directory must not be a symlink")
    if action == "prepare":
        prepare(build, args[0])
    elif action == "stage":
        stage(build, args[0])
    elif action == "clean":
        if build.exists():
            shutil.rmtree(build)
    elif action == "check-python":
        check_python()
    else:
        raise ValueError(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
