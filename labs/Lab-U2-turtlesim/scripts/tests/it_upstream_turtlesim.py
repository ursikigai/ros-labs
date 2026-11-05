"""End-to-end test of the ORIGINAL ros/ros_tutorials turtlesim (branch jazzy), BUILT FROM SOURCE from upstream/ros_tutorials-jazzy.

Not course code: this is the real turtlesim (C++, Qt5) compiled on this machine by scripts/build_upstream.bat.
  A. turtlesim_node : motion, pose, teleport, spawn/kill, pen, and the rotate_absolute action.
  B. mimic (tutorial node) : turtle 2 copies turtle 1 across two turtlesim instances.
Run:  pixi run test-turtlesim   (after  pixi run build-turtlesim)
"""
import math
import time

import harness  # noqa: F401
import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Twist, Vector3
from rclpy.action import ActionClient
from rclpy.node import Node
from turtlesim.action import RotateAbsolute
from turtlesim.msg import Pose
from turtlesim.srv import Kill, SetPen, Spawn, TeleportAbsolute, TeleportRelative


class Probe(Node):
    def __init__(self):
        super().__init__("turtlesim_probe")
        self.pose = {}
        self.pubs = {}

    def watch(self, ns):
        self.pubs[ns] = self.create_publisher(Twist, f"{ns}/turtle1/cmd_vel", 10)
        self.create_subscription(Pose, f"{ns}/turtle1/pose", lambda m, ns=ns: self.pose.__setitem__(ns, m), 10)

    def call(self, srv_type, name, request, timeout=20.0):
        client = self.create_client(srv_type, name)
        if not client.wait_for_service(timeout_sec=timeout):
            return None
        fut = client.call_async(request)
        harness.wait_until(self, fut.done, timeout=timeout)
        return fut.result() if fut.done() else None

    def drive(self, ns, v, w, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.pubs[ns].publish(Twist(linear=Vector3(x=float(v)), angular=Vector3(z=float(w))))
            rclpy.spin_once(self, timeout_sec=0.05)
        self.pubs[ns].publish(Twist())
        harness.wait_until(self, lambda: False, timeout=1.5)  # let turtlesim finish moving


def main():
    c = harness.Checker("Original ros_tutorials turtlesim (jazzy), built from source")
    share = get_package_share_directory("turtlesim")
    c.check("upstream_ws" in share, f"turtlesim is the one built from the clone ({share.split('ros2-pbl-course')[-1]})")
    rclpy.init()

    # ------------------------------------------------------------------ A. a single turtlesim_node
    with harness.process("ros2", "run", "turtlesim", "turtlesim_node"):
        p = Probe()
        p.watch("")
        up = harness.wait_until(p, lambda: "" in p.pose, timeout=90.0)
        c.check(up, "turtlesim_node starts and publishes /turtle1/pose")
        start = p.pose[""]
        c.check(abs(start.x - 5.5444) < 0.01 and abs(start.y - 5.5444) < 0.01 and abs(start.theta) < 1e-3,
                f"turtle starts in the middle of the 11x11 window ({start.x:.3f}, {start.y:.3f}, theta {start.theta:.2f})")

        p.drive("", 2.0, 0.0, 1.0)
        moved = p.pose[""].x - start.x
        c.check(1.5 < moved < 2.6, f"cmd_vel linear.x = 2.0 for 1 s moves the turtle about 2 units (moved {moved:.2f})")

        r = p.call(TeleportAbsolute, "/turtle1/teleport_absolute", TeleportAbsolute.Request(x=2.0, y=3.0, theta=0.5))
        harness.wait_until(p, lambda: False, timeout=0.5)
        c.check(r is not None and abs(p.pose[""].x - 2.0) < 0.05 and abs(p.pose[""].y - 3.0) < 0.05 and abs(p.pose[""].theta - 0.5) < 0.05,
                f"teleport_absolute puts it at (2, 3, 0.5): now ({p.pose[''].x:.2f}, {p.pose[''].y:.2f}, {p.pose[''].theta:.2f})")

        r = p.call(TeleportRelative, "/turtle1/teleport_relative", TeleportRelative.Request(linear=1.0, angular=0.0))
        harness.wait_until(p, lambda: False, timeout=0.5)
        dx, dy = p.pose[""].x - 2.0, p.pose[""].y - 3.0
        c.check(r is not None and abs(dx - math.cos(0.5)) < 0.05 and abs(dy - math.sin(0.5)) < 0.05,
                f"teleport_relative moves 1 unit along the heading (moved {dx:.2f}, {dy:.2f}; expected 0.88, 0.48)")

        spawned = p.call(Spawn, "/spawn", Spawn.Request(x=8.0, y=8.0, theta=0.0, name="t2"))
        c.check(spawned is not None and spawned.name == "t2", f"spawn creates a named turtle ({getattr(spawned, 'name', None)!r})")
        again = p.call(Spawn, "/spawn", Spawn.Request(x=1.0, y=1.0, theta=0.0, name="t2"))
        c.check(again is not None and again.name == "", f"spawning a duplicate name is refused (reply name = {getattr(again, 'name', None)!r})")
        killed = p.call(Kill, "/kill", Kill.Request(name="t2"))
        respawn = p.call(Spawn, "/spawn", Spawn.Request(x=8.0, y=8.0, theta=0.0, name="t2"))
        c.check(killed is not None and respawn is not None and respawn.name == "t2", "kill frees the name so it can be spawned again")

        pen = p.call(SetPen, "/turtle1/set_pen", SetPen.Request(r=255, g=0, b=0, width=3, off=0))
        c.check(pen is not None, "set_pen service answers")

        client = ActionClient(p, RotateAbsolute, "/turtle1/rotate_absolute")
        c.check(client.wait_for_server(timeout_sec=20.0), "rotate_absolute action server is available")
        fut = client.send_goal_async(RotateAbsolute.Goal(theta=1.5))
        harness.wait_until(p, fut.done, timeout=15.0)
        handle = fut.result()
        res_fut = handle.get_result_async()
        harness.wait_until(p, res_fut.done, timeout=30.0)
        res = res_fut.result()
        harness.wait_until(p, lambda: False, timeout=0.5)
        c.check(res is not None and res.status == GoalStatus.STATUS_SUCCEEDED and abs(p.pose[""].theta - 1.5) < 0.06,
                f"rotate_absolute turns the turtle to 1.5 rad (theta now {p.pose[''].theta:.3f}, status {getattr(res, 'status', None)})")
        p.destroy_node()
    time.sleep(3.0)

    # ------------------------------------------------------------------ B. the tutorial's `mimic` node across two turtlesim instances
    with harness.process("ros2", "run", "turtlesim", "turtlesim_node", "--ros-args", "-r", "__ns:=/turtlesim1"), \
         harness.process("ros2", "run", "turtlesim", "turtlesim_node", "--ros-args", "-r", "__ns:=/turtlesim2"), \
         harness.process("ros2", "run", "turtlesim", "mimic", "--ros-args", "-r", "input/pose:=/turtlesim1/turtle1/pose",
                         "-r", "output/cmd_vel:=/turtlesim2/turtle1/cmd_vel"):
        p = Probe()
        p.watch("/turtlesim1")
        p.watch("/turtlesim2")
        up = harness.wait_until(p, lambda: "/turtlesim1" in p.pose and "/turtlesim2" in p.pose, timeout=90.0)
        c.check(up, "two turtlesim instances and the mimic node are up")
        t2_before = p.pose["/turtlesim2"]
        harness.wait_until(p, lambda: False, timeout=3.0)  # let mimic discover both ends
        p.drive("/turtlesim1", 1.5, 1.0, 4.0)
        t2_after = p.pose["/turtlesim2"]
        moved2 = math.hypot(t2_after.x - t2_before.x, t2_after.y - t2_before.y)
        turned2 = abs(t2_after.theta - t2_before.theta)
        c.check(moved2 > 1.0, f"mimic: turtle 2 moved although only turtle 1 was driven (moved {moved2:.2f} units)")
        c.check(turned2 > 0.3, f"mimic: turtle 2 also turned like turtle 1 (theta changed by {turned2:.2f} rad)")
        p.destroy_node()

    rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
