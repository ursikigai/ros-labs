"""End-to-end test of Isaac project 1 (drive DiffBot in Isaac Sim from ROS 2).

Starts Isaac Sim headless in its own environment, then talks to it from this ROS 2 Jazzy process over DDS:
checks the topics the simulator publishes, drives 0.2 m/s for 4 simulated seconds and turns on the spot.
Needs the NVIDIA GPU. First start can take a few minutes while Isaac Sim compiles its shader cache.
"""
import math
import sys
import time

import isaac_harness as ih
import harness
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import JointState
from tf2_msgs.msg import TFMessage


def main():
    chk = harness.Checker("Isaac project 1: drive DiffBot in Isaac Sim from ROS 2")
    rclpy.init()
    node = Node("it_isaac_p1")
    clock = ih.SimClock(node)
    state = {"odom": None, "joints": None, "frames": set()}

    def on_odom(m):
        state["odom"] = m

    def on_tf(m):
        for t in m.transforms:
            state["frames"].add((t.header.frame_id, t.child_frame_id))

    node.create_subscription(Odometry, "/odom", on_odom, 10)
    node.create_subscription(TFMessage, "/tf", on_tf, 10)
    node.create_subscription(JointState, "/joint_states", lambda m: state.__setitem__("joints", m), 10)
    pub = node.create_publisher(Twist, "/cmd_vel", 10)

    with ih.isaac(r"isaac\scripts\p1_drive.py", log_name="isaac_p1"):
        up = harness.wait_until(node, lambda: clock.now is not None and state["odom"] is not None, timeout=420)
        chk.check(up, "Isaac Sim started and publishes /clock and /odom (first start can take minutes)")
        if not up:
            chk.finish()
            return chk.failures
        harness.wait_until(node, lambda: state["joints"] is not None and len(state["frames"]) >= 5, timeout=30)

        # --- the topics the course's own robot also has
        chk.check(("odom", "base_footprint") in state["frames"], "TF odom -> base_footprint")
        links = {c for _, c in state["frames"]}
        chk.check({"left_wheel_link", "right_wheel_link", "lidar_link", "base_link", "caster_link"} <= links,
                   f"TF base_footprint -> every link of the URDF ({sorted(links - {'base_footprint'})})")
        names = set(state["joints"].name) if state["joints"] else set()
        chk.check({"left_wheel_joint", "right_wheel_joint"} <= names, f"/joint_states carries both wheel joints ({sorted(names)})")
        t0 = clock.now
        harness.wait_until(node, lambda: clock.now - t0 > 1.0, timeout=60)
        chk.check(clock.now - t0 > 1.0, "simulated time advances")

        # --- let the robot settle on the ground, then note the start pose
        ih.spin_sim_seconds(node, clock, 1.5)
        o0 = state["odom"].pose.pose
        x0, y0, yaw0 = o0.position.x, o0.position.y, ih.yaw_of(o0.orientation)
        chk.check(abs(x0) < 0.05 and abs(y0) < 0.05, f"robot rests at the spawn point (x={x0:.3f}, y={y0:.3f})")

        # --- drive straight: 0.2 m/s for 4 simulated seconds -> about 0.8 m
        cmd = Twist()
        cmd.linear.x = 0.2
        sim_s = ih.spin_sim_seconds(node, clock, 4.0, on_tick=lambda: pub.publish(cmd))
        pub.publish(Twist())
        ih.spin_sim_seconds(node, clock, 1.0)
        o1 = state["odom"].pose.pose
        dist = math.hypot(o1.position.x - x0, o1.position.y - y0)
        dyaw = ih.wrap(ih.yaw_of(o1.orientation) - yaw0)
        print(f"drove {dist:.3f} m in {sim_s:.1f} simulated s, heading changed {dyaw:+.3f} rad", flush=True)
        chk.check(0.6 < dist < 1.0, f"/cmd_vel 0.2 m/s for 4 s moved the robot {dist:.2f} m (expected about 0.8)")
        chk.check(abs(dyaw) < 0.15, f"it kept its heading (changed {dyaw:+.3f} rad)")
        chk.check(state["odom"].child_frame_id == "base_footprint" and state["odom"].header.frame_id == "odom",
                  "/odom uses frames odom -> base_footprint")

        # --- turn on the spot: 0.5 rad/s for 3 simulated seconds -> about 1.5 rad
        yaw1 = ih.yaw_of(o1.orientation)
        cmd = Twist()
        cmd.angular.z = 0.5
        ih.spin_sim_seconds(node, clock, 3.0, on_tick=lambda: pub.publish(cmd))
        pub.publish(Twist())
        ih.spin_sim_seconds(node, clock, 1.0)
        o2 = state["odom"].pose.pose
        turned = ih.wrap(ih.yaw_of(o2.orientation) - yaw1)
        shift = math.hypot(o2.position.x - o1.position.x, o2.position.y - o1.position.y)
        print(f"turned {turned:+.3f} rad, moved {shift:.3f} m while turning", flush=True)
        chk.check(1.1 < turned < 1.9, f"/cmd_vel 0.5 rad/s for 3 s turned the robot {turned:.2f} rad (expected about 1.5)")
        chk.check(shift < 0.15, f"it turned about its centre (moved {shift:.2f} m)")

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
