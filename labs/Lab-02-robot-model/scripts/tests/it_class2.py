"""Class 2 end-to-end test: the DiffBot URDF running under robot_state_publisher (+ RViz2).

Checks that /robot_description is published, fixed-joint TFs resolve, and that publishing
joint states makes the continuous wheel joints appear in TF. Finally starts RViz2 with the
course config (offscreen) and verifies it stays alive.
Run:  pixi run test-class2
"""
import os
import time

import harness  # noqa: F401
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from rclpy.time import Time
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener


class Probe(Node):
    def __init__(self):
        super().__init__("class2_probe")
        self.description = None
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, "robot_description", lambda m: setattr(self, "description", m.data), latched)
        self.joint_pub = self.create_publisher(JointState, "joint_states", 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def publish_joints(self, left, right):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ["left_wheel_joint", "right_wheel_joint"]
        msg.position = [left, right]
        self.joint_pub.publish(msg)


def main():
    c = harness.Checker("Class 2 - robot model (URDF/Xacro, TF, RViz)")
    with harness.launched(
        "diffbot_description", "display.launch.py", "gui:=false", "rviz:=false", log_name="class2"
    ):
        rclpy.init()
        probe = Probe()
        c.check(
            harness.wait_until(probe, lambda: probe.description is not None, timeout=90.0),
            "/robot_description is published",
        )
        c.check(
            probe.description is not None and 'name="diffbot"' in probe.description,
            "robot_description contains the DiffBot model",
        )
        c.check(
            harness.wait_until(
                probe, lambda: probe.tf_buffer.can_transform("base_footprint", "lidar_link", Time()), timeout=30.0
            ),
            "fixed-joint TF base_footprint -> lidar_link resolves",
        )
        # Wheel joints are continuous: they only appear in TF once joint states exist.
        end = time.monotonic() + 15.0
        ok = False
        while time.monotonic() < end and not ok:
            probe.publish_joints(1.0, -1.0)
            rclpy.spin_once(probe, timeout_sec=0.1)
            ok = probe.tf_buffer.can_transform("base_link", "left_wheel_link", Time())
        c.check(ok, "continuous-joint TF base_link -> left_wheel_link appears after joint_states")
        if ok:
            t = probe.tf_buffer.lookup_transform("base_link", "left_wheel_link", Time()).transform.translation
            c.check(abs(t.y - 0.15) < 1e-6 and abs(t.x) < 1e-6, f"left wheel is 0.15 m to the left (y={t.y:.3f})")
        probe.destroy_node()
        rclpy.shutdown()

    # RViz2 smoke test: load the course config and make sure it does not crash.
    # (QT_QPA_PLATFORM=offscreen comes from the pixi task env, so no window opens.)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    with harness.launched(
        "diffbot_description", "display.launch.py", "gui:=false", "rviz:=true", log_name="class2_rviz", startup_s=25.0
    ) as proc:
        c.check(proc.poll() is None, "launch with RViz2 is still running after 25 s")
    c.finish()


if __name__ == "__main__":
    main()
