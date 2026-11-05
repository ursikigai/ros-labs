"""Helpers for the end-to-end tests of the Isaac Sim projects.

Isaac Sim runs as a separate process (its own Python 3.11 pixi workspace in isaac/). The test process is the course's
ROS 2 Jazzy environment, so the two meet over DDS exactly like two machines. That is also why the Isaac process gets a
CLEAN environment: the conda variables of the ROS 2 environment (PYTHONPATH, PATH entries with Jazzy DLLs, ...) must
not leak into it.
"""
import os
import subprocess
import time
from contextlib import contextmanager

import harness  # noqa: F401  (sets ROS_DOMAIN_ID before rclpy is initialised)

ISAAC_DOMAIN_ID = "78"
os.environ["ROS_DOMAIN_ID"] = ISAAC_DOMAIN_ID
os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")  # the bridge in Isaac Sim uses Fast DDS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DROP_PREFIXES = ("CONDA", "PIXI", "AMENT", "COLCON", "ROS_", "RMW_", "PYTHON", "CMAKE_PREFIX", "OMNI_KIT")


def _registry_path():
    """The Windows PATH as a fresh login would see it (system + user), without the conda environment."""
    import winreg

    parts = []
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, r"Environment")):
        try:
            with winreg.OpenKey(hive, sub) as key:
                parts.append(os.path.expandvars(winreg.QueryValueEx(key, "Path")[0]))
        except OSError:
            pass
    return ";".join(parts)


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(_DROP_PREFIXES)}
    env["PATH"] = _registry_path()
    env["ROS_DOMAIN_ID"] = ISAAC_DOMAIN_ID
    return env


@contextmanager
def isaac(script, *script_args, log_name="isaac"):
    """Start `run_isaac.ps1 <script> ...` and ALWAYS kill the whole process tree afterwards."""
    log_dir = os.path.join(ROOT, "test_logs")
    os.makedirs(log_dir, exist_ok=True)
    log = open(os.path.join(log_dir, f"{log_name}.log"), "w")
    cmd = ["powershell", "-NoProfile", "-File", os.path.join(ROOT, "scripts", "isaac", "run_isaac.ps1"), script, *script_args]
    proc = subprocess.Popen(cmd, cwd=ROOT, env=clean_env(), stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        yield proc
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.close()


def yaw_of(q):
    import math

    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def wrap(a):
    import math

    return (a + math.pi) % (2 * math.pi) - math.pi


class SimClock:
    """Tracks /clock so a test can pace itself in SIMULATED seconds (Isaac Sim does not run at wall-clock speed)."""

    def __init__(self, node):
        from rosgraph_msgs.msg import Clock

        self.now = None
        self.first = None
        node.create_subscription(Clock, "/clock", self._cb, 10)

    def _cb(self, msg):
        self.now = msg.clock.sec + msg.clock.nanosec * 1e-9
        if self.first is None:
            self.first = self.now


def spin_sim_seconds(node, clock, seconds, on_tick=None, wall_timeout=300.0):
    """Spin until `seconds` of simulated time have passed; calls on_tick() roughly every 50 ms of wall time."""
    import rclpy

    start = clock.now
    t0 = time.monotonic()
    while clock.now is not None and clock.now - start < seconds and time.monotonic() - t0 < wall_timeout:
        if on_tick:
            on_tick()
        rclpy.spin_once(node, timeout_sec=0.05)
    return clock.now - start if (clock.now is not None and start is not None) else 0.0


ARTIFACTS = os.path.join(ROOT, "build", "isaac")


def save_png(path, rgb):
    """Write an HxWx3 uint8 array as a PNG (no imaging library needed)."""
    import struct
    import zlib

    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)