"""End-to-end test of the ORIGINAL Packt 'ROS 2 from Scratch' chapter-9 code (upstream/ros2-from-scratch/ch9).

Nothing here is course code: the nodes, interfaces and launch files under test are the cloned repository's own
(Python + C++ packages, built by scripts/build_upstream.bat). Run:  pixi run test-packt

  A. number_app.launch.py : two Python publishers (one configured inline, one from a YAML file) feed a C++ counter.
  B. turtlesim_control.launch.py : two namespaced turtlesims, each driven by the Python turtle_controller.
  C. count_until_server (Python and C++ versions) : the chapter-7 action: accept, feedback, result, reject, cancel.
"""
import math
import subprocess
import time
from contextlib import contextmanager

import harness  # noqa: F401  (sets ROS_DOMAIN_ID before rclpy)
import rclpy
from action_msgs.msg import GoalStatus
from example_interfaces.msg import Int64
from my_robot_interfaces.action import CountUntil
from my_robot_interfaces.srv import ActivateTurtle, ResetCounter
from rclpy.action import ActionClient
from rclpy.node import Node
from turtlesim.msg import Pose


class Probe(Node):
    def __init__(self):
        super().__init__("packt_probe")
        self.numbers = []
        self.poses = {"t1": None, "t2": None}
        self.travelled = {"t1": 0.0, "t2": 0.0}
        self.create_subscription(Int64, "/abc/number", lambda m: self.numbers.append(m.data), 10)
        for ns in ("t1", "t2"):
            self.create_subscription(Pose, f"/{ns}/turtle1/pose", lambda m, ns=ns: self.on_pose(ns, m), 10)
        self.reset_client = self.create_client(ResetCounter, "/abc/reset_counter")
        self.activate_client = self.create_client(ActivateTurtle, "/t1/activate_turtle")

    def on_pose(self, ns, msg):
        prev = self.poses[ns]
        if prev is not None:
            self.travelled[ns] += math.hypot(msg.x - prev.x, msg.y - prev.y)
        self.poses[ns] = msg

    def call(self, client, request, timeout=15.0):
        future = client.call_async(request)
        harness.wait_until(self, future.done, timeout=timeout)
        return future.result() if future.done() else None

    def spin_seconds(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)


@contextmanager
def node_process(pkg, exe):
    """`ros2 run pkg exe` in a subprocess that is always killed (whole tree) afterwards."""
    proc = subprocess.Popen(["ros2", "run", pkg, exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        yield proc
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def check_action_server(c, label, pkg):
    """Accept / feedback / result / reject / cancel against the chapter-7 count_until server of `pkg`."""
    # The Python and C++ servers share the action name. Make sure the previous one has really left the ROS graph,
    # otherwise the client can still "see" the dead server and send its goal into the void.
    gone_node = Node(f"gone_probe_{pkg}")
    gone_client = ActionClient(gone_node, CountUntil, "count_until")
    harness.wait_until(gone_node, lambda: not gone_client.server_is_ready(), timeout=60.0)
    gone_node.destroy_node()
    with node_process(pkg, "count_until_server"):
        node = Node(f"action_probe_{pkg}")
        client = ActionClient(node, CountUntil, "count_until")
        c.check(client.wait_for_server(timeout_sec=90.0), f"[{label}] action server is up")

        feedback = []
        goal = CountUntil.Goal(target_number=5, delay=0.2)
        fut = client.send_goal_async(goal, feedback_callback=lambda m: feedback.append(m.feedback.current_number))
        harness.wait_until(node, fut.done, timeout=15.0)
        handle = fut.result()
        c.check(handle is not None and handle.accepted, f"[{label}] goal 'count to 5' accepted")
        res_fut = handle.get_result_async()
        harness.wait_until(node, res_fut.done, timeout=30.0)
        res = res_fut.result()
        c.check(res is not None and res.status == GoalStatus.STATUS_SUCCEEDED and res.result.reached_number == 5,
                f"[{label}] result: succeeded, reached_number = {getattr(getattr(res, 'result', None), 'reached_number', None)}")
        c.check(len(feedback) >= 3, f"[{label}] feedback was streamed while counting ({len(feedback)} messages)")

        fut = client.send_goal_async(CountUntil.Goal(target_number=-1, delay=0.1))
        harness.wait_until(node, fut.done, timeout=15.0)
        c.check(fut.result() is not None and not fut.result().accepted, f"[{label}] goal with a negative target is rejected")

        fut = client.send_goal_async(CountUntil.Goal(target_number=20, delay=0.3))
        harness.wait_until(node, fut.done, timeout=15.0)
        handle = fut.result()
        harness.wait_until(node, lambda: False, timeout=1.2)
        cancel_fut = handle.cancel_goal_async()
        harness.wait_until(node, cancel_fut.done, timeout=15.0)
        res_fut = handle.get_result_async()
        harness.wait_until(node, res_fut.done, timeout=30.0)
        res = res_fut.result()
        c.check(res is not None and res.status == GoalStatus.STATUS_CANCELED and res.result.reached_number < 20,
                f"[{label}] a running goal can be cancelled (stopped at {getattr(getattr(res, 'result', None), 'reached_number', None)} of 20)")
        node.destroy_node()
    time.sleep(2.0)


def param_get(node_name, param, tries=4):
    """`ros2 param get`; without the daemon discovery is brief, so allow a spin time and retry."""
    out = ""
    for _ in range(tries):
        out = subprocess.run(["ros2", "param", "get", node_name, param, "--no-daemon", "--spin-time", "4"],
                             capture_output=True, text=True, timeout=90).stdout.strip()
        if "value is" in out:
            break
    return out


def main():
    c = harness.Checker("Original Packt 'ROS 2 from Scratch' ch9 (cloned repo, built unmodified)")
    rclpy.init()

    # ------------------------------------------------------------------ A. number_app (Python + C++)
    with harness.launched("my_robot_bringup", "number_app.launch.py", log_name="packt_numbers"):
        probe = Probe()
        up = harness.wait_until(probe, lambda: probe.reset_client.service_is_ready() and {3, 4} <= set(probe.numbers), timeout=90.0)
        c.check(up, "number_app is up: C++ number_counter answers and both Python publishers are publishing")
        c.check({3, 4} <= set(probe.numbers), f"launch-time parameters reached the nodes (values seen on /abc/number: {sorted(set(probe.numbers))})")

        bad = probe.call(probe.reset_client, ResetCounter.Request(reset_value=-5))
        c.check(bad is not None and bad.success is False and "negative" in bad.message,
                f"C++ service rejects a negative reset ({bad.message!r})" if bad else "no reply")
        high = probe.call(probe.reset_client, ResetCounter.Request(reset_value=10**6))
        c.check(high is not None and high.success is False and "lower" in high.message,
                f"C++ service rejects a reset above the current count ({high.message!r})" if high else "no reply")
        ok = probe.call(probe.reset_client, ResetCounter.Request(reset_value=0))
        c.check(ok is not None and ok.success is True and ok.message == "Success",
                f"C++ service accepts a valid reset to 0 ({ok.message!r})" if ok else "no reply")
        probe.destroy_node()

    time.sleep(3.0)  # let the previous stack disappear from DDS discovery

    # ------------------------------------------------------------------ B. turtlesim_control (Python, 2 namespaces)
    with harness.launched("my_robot_bringup", "turtlesim_control.launch.py", log_name="packt_turtles"):
        probe = Probe()
        up = harness.wait_until(probe, lambda: probe.poses["t1"] and probe.poses["t2"] and probe.activate_client.service_is_ready(), timeout=90.0)
        c.check(up, "both namespaced turtlesims and the controller service are up")

        c.check("128" in param_get("/t1/turtlesim", "background_r"), "YAML parameter reached /t1/turtlesim (background_r = 128)")
        c.check("128" in param_get("/t2/turtlesim", "background_g"), "YAML parameter reached /t2/turtlesim (background_g = 128)")

        probe.travelled = {"t1": 0.0, "t2": 0.0}
        probe.spin_seconds(10.0)
        d1, d2 = probe.travelled["t1"], probe.travelled["t2"]
        print(f"distance travelled in 10 s:  t1 (turtle_velocity 1.5) = {d1:.1f}   t2 (turtle_velocity 0.5) = {d2:.1f}")
        c.check(d1 > 2.0 and d2 > 0.5, "both controllers drive their turtle")
        c.check(d1 > 1.8 * d2, "the faster-configured turtle (1.5) travelled much farther than the slow one (0.5)")

        reply = probe.call(probe.activate_client, ActivateTurtle.Request(activate=False))
        c.check(reply is not None and reply.message == "Stopping the turtle", f"activate_turtle(False) answers ({getattr(reply, 'message', None)!r})")
        probe.spin_seconds(3.0)  # turtlesim keeps the last command for ~1 s
        probe.travelled["t1"] = probe.travelled["t2"] = 0.0
        probe.spin_seconds(3.0)
        c.check(probe.travelled["t1"] < 0.05, f"t1 stopped after being deactivated (moved {probe.travelled['t1']:.3f})")
        c.check(probe.travelled["t2"] > 0.3, f"t2 kept moving (moved {probe.travelled['t2']:.2f})")
        probe.destroy_node()

    time.sleep(3.0)

    # ------------------------------------------------------------------ C. action servers (chapter 7): Python and C++
    check_action_server(c, "python", "my_py_pkg")
    check_action_server(c, "c++   ", "my_cpp_pkg")

    rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
