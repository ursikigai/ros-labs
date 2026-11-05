"""Shared helpers for the end-to-end class tests.

Every test runs the real `ros2 launch` in a subprocess inside an isolated DDS domain and
ALWAYS kills the whole process tree afterwards, so a failing test never leaves nodes behind.
"""
import os
import subprocess
import sys
import time
from contextlib import contextmanager

DOMAIN_ID = "77"
os.environ["ROS_DOMAIN_ID"] = DOMAIN_ID  # must be set before rclpy.init in the test process


@contextmanager
def launched(*launch_args, log_name="launch", startup_s=2.0):
    """Start `ros2 launch <args>` and yield the Popen. Output goes to a log file."""
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_logs")
    os.makedirs(log_dir, exist_ok=True)
    log = open(os.path.join(log_dir, f"{log_name}.log"), "w")
    os.environ["PYTHONUNBUFFERED"] = "1"  # otherwise node logs sit in a buffer when redirected
    proc = subprocess.Popen(
        ["ros2", "launch", *launch_args],
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        time.sleep(startup_s)
        if proc.poll() is not None:
            raise RuntimeError(f"launch exited early (code {proc.returncode}); see {log.name}")
        yield proc
    finally:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.close()


@contextmanager
def process(*cmd):  # noqa: D401
    """Run an arbitrary command (e.g. `ros2 run pkg exe ...`) and ALWAYS kill its whole process tree afterwards."""
    proc = subprocess.Popen(list(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        yield proc
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_until(node, predicate, timeout=60.0):
    """Spin `node` until predicate() is truthy. Returns True, or False on timeout."""
    import rclpy

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        rclpy.spin_once(node, timeout_sec=0.1)
    return bool(predicate())


class Checker:
    """Collects PASS/FAIL lines and produces a process exit code."""

    def __init__(self, title):
        self.title = title
        self.failures = 0
        print(f"=== {title} ===")

    def check(self, ok, message):
        print(("PASS  " if ok else "FAIL  ") + message)
        if not ok:
            self.failures += 1

    def finish(self):
        print(f"--- {self.title}: {'ALL PASSED' if self.failures == 0 else str(self.failures) + ' FAILED'}")
        sys.exit(1 if self.failures else 0)
