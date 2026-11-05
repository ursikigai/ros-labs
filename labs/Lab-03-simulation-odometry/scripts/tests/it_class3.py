"""Class 3 end-to-end test: simulator + robot model + odometry.

Drives DiffBot forward then rotates it, and verifies that
  * /joint_states, /scan, /odom, /ground_truth all publish,
  * the TF tree map -> odom -> base_footprint -> base_link -> lidar_link resolves,
  * wheel odometry agrees with the simulator's ground truth.
Run:  pixi run test-class3
"""
import math
import time

import harness  # noqa: F401  (sets ROS_DOMAIN_ID before rclpy)
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState, LaserScan
from tf2_ros import Buffer, TransformListener

START = (1.0, 1.0, 0.0)


class Probe(Node):
    def __init__(self):
        super().__init__("class3_probe")
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.odom = self.truth = self.scan = self.joints = None
        self.create_subscription(Odometry, "odom", lambda m: setattr(self, "odom", m), 10)
        self.create_subscription(Odometry, "ground_truth", lambda m: setattr(self, "truth", m), 10)
        self.create_subscription(LaserScan, "scan", lambda m: setattr(self, "scan", m), 10)
        self.create_subscription(JointState, "joint_states", lambda m: setattr(self, "joints", m), 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def spin_for(self, seconds, v=0.0, w=0.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.cmd_pub.publish(Twist(linear=_v(x=v), angular=_v(z=w)))
            rclpy.spin_once(self, timeout_sec=0.05)


def _v(x=0.0, z=0.0):
    from geometry_msgs.msg import Vector3

    return Vector3(x=float(x), y=0.0, z=float(z))


def yaw(q):
    return 2.0 * math.atan2(q.z, q.w)


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def main():
    c = harness.Checker("Class 3 - simulator, model and odometry")
    with harness.launched("diffbot_bringup", "sim.launch.py", log_name="class3"):
        rclpy.init()
        probe = Probe()
        # Windows start-up is slow (first-run DLL loading): wait for readiness, don't guess.
        ready = harness.wait_until(
            probe,
            lambda: probe.joints and probe.scan and probe.odom and probe.truth
            and probe.tf_buffer.can_transform("map", "lidar_link", Time()),
            timeout=90.0,
        )
        c.check(ready, "stack came up (topics + full TF chain) within 90 s")
        probe.spin_for(1.0)

        c.check(probe.joints is not None, "/joint_states is publishing")
        c.check(probe.scan is not None and len(probe.scan.ranges) == 360, "/scan has 360 rays")
        c.check(
            probe.scan is not None and any(math.isfinite(r) for r in probe.scan.ranges),
            "/scan sees the walls (finite ranges)",
        )
        c.check(probe.odom is not None, "/odom is publishing")
        c.check(probe.truth is not None, "/ground_truth is publishing")

        for parent, child in [
            ("map", "odom"),
            ("odom", "base_footprint"),
            ("base_footprint", "base_link"),
            ("base_link", "lidar_link"),
            ("map", "lidar_link"),
        ]:
            ok = probe.tf_buffer.can_transform(parent, child, Time())
            c.check(ok, f"TF {parent} -> {child} resolves")

        # Drive: 4 s forward at 0.2 m/s (0.8 m), then 3 s rotating at 0.5 rad/s (1.5 rad).
        probe.spin_for(4.0, v=0.2)
        probe.spin_for(3.0, w=0.5)
        probe.spin_for(1.0)  # stop and settle
        rclpy.spin_once(probe, timeout_sec=0.2)

        ox, oy, oth = probe.odom.pose.pose.position.x, probe.odom.pose.pose.position.y, yaw(probe.odom.pose.pose.orientation)
        gx, gy, gth = (
            probe.truth.pose.pose.position.x - START[0],
            probe.truth.pose.pose.position.y - START[1],
            wrap(yaw(probe.truth.pose.pose.orientation) - START[2]),
        )
        print(f"odom   : x={ox:.3f} y={oy:.3f} yaw={oth:.3f}")
        print(f"truth  : x={gx:.3f} y={gy:.3f} yaw={gth:.3f}")
        c.check(abs(gx) > 0.5, f"robot actually moved (truth x = {gx:.2f} m)")
        c.check(abs(ox - gx) < 0.03 and abs(oy - gy) < 0.03, "odom position within 3 cm of ground truth")
        c.check(abs(wrap(oth - gth)) < 0.03, "odom heading within 0.03 rad of ground truth")

        # Safety watchdog: with no more commands the robot must stop by itself.
        before = probe.truth.pose.pose.position.x
        probe.spin_for(0.0)
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            rclpy.spin_once(probe, timeout_sec=0.05)  # no cmd_vel published
        c.check(
            abs(probe.truth.pose.pose.position.x - before) < 0.01,
            "robot is stationary once commands stop (watchdog)",
        )
        probe.destroy_node()
        rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
