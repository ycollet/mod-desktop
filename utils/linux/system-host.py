#!/usr/bin/env python3

"""Run MOD's standalone clients without starting or stopping the audio server."""

import ctypes
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time


def open_jack():
    jack = ctypes.CDLL("libjack.so.0")
    jack.jack_client_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    jack.jack_client_open.restype = ctypes.c_void_p
    jack.jack_port_by_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    jack.jack_port_by_name.restype = ctypes.c_void_p
    jack.jack_client_close.argtypes = [ctypes.c_void_p]
    jack.jack_client_close.restype = ctypes.c_int
    status = ctypes.c_int()
    # JackNoStartServer | JackUseExactName also prevents a second supervisor.
    client = jack.jack_client_open(b"mod-desktop-system", 1 | 2, ctypes.byref(status))
    if not client:
        raise RuntimeError(f"Cannot connect to system JACK/PipeWire (JACK status {status.value})")
    return jack, client


def main():
    root = Path(__file__).resolve().parent
    children = []
    jack = None
    client = None
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        port = int(os.environ.get("MOD_DEVICE_HOST_PORT", "18182"))
        if not 1 <= port <= 65534:
            raise ValueError("MOD_DEVICE_HOST_PORT must be between 1 and 65534")
        jack, client = open_jack()
        for name in (b"mod-host:in1", b"mod-midi-merger:out", b"mod-midi-broadcaster:in"):
            if jack.jack_port_by_name(client, name):
                raise RuntimeError(f"An existing MOD client owns {name.decode()}; stop it first")
        commands = [
            [str(root / "mod-midi-merger")],
            [str(root / "mod-midi-broadcaster")],
            [str(root / "mod-host-native"), "-n", "-p", str(port)],
        ]
        if os.environ.get("MOD_LOG", "0") != "0":
            commands[-1].append("-v")
        with selectors.DefaultSelector() as selector:
            for command in commands[:2]:
                child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                children.append(child)
                selector.register(child.stdout, selectors.EVENT_READ)

            deadline = time.monotonic() + 15
            pending = b""
            ready = False
            host = None
            while not stopping:
                for key, _ in selector.select(timeout=0.05):
                    data = os.read(key.fileobj.fileno(), 4096)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    if host is not None and key.fileobj is host.stdout:
                        pending = (pending + data)[-4096:]
                        ready = ready or b"mod-host ready!" in pending
                for child in children:
                    if child.poll() is not None:
                        raise RuntimeError(
                            f"{Path(child.args[0]).name} exited with status {child.returncode}. "
                            "Check that the system JACK/PipeWire server is running."
                        )
                if host is None and all(jack.jack_port_by_name(client, name) for name in (
                    b"mod-midi-merger:out", b"mod-midi-broadcaster:in",
                )):
                    host = subprocess.Popen(commands[-1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    children.append(host)
                    selector.register(host.stdout, selectors.EVENT_READ)
                if not ready and time.monotonic() >= deadline:
                    raise RuntimeError("Timed out waiting for MOD clients to connect to system JACK/PipeWire")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"MOD Desktop system audio error: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 0.25
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            if child.stdout is not None:
                child.stdout.close()
        if client is not None:
            jack.jack_client_close(client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
