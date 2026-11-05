"""End-to-end test of Isaac project 2: a lidar in Isaac Sim, read by the course's own (unchanged) obstacle avoider.

Checks the /scan message against the known room, then starts `ros2 run diffbot_navigation obstacle_avoider` and watches
the robot wander for 60 simulated seconds: it must travel, stay inside the room and never come closer than 0.2 m to a wall
or box (judged from /odom and the known geometry, independent of the lidar).
"""
import math
import os
import sys

import isaac_harness as ih
import harness
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

HALF_W, HALF_D = 4.0, 3.0
BOXES = [((1.5, 1.0), (0.3, 0.3)), ((-1.5, -1.0), (0.3, 0.3))]  # centre, half size
ROBOT_RADIUS = 0.17  # body is 0.30 x 0.20 m; the corner is 0.18 m from the centre


def clearance(x, y):
    """Distance from a point to the nearest wall or box edge (negative inside an obstacle)."""
    d = min(HALF_W - abs(x), HALF_D - abs(y))
    for (cx, cy), (hx, hy) in BOXES:
        dx, dy = max(abs(x - cx) - hx, 0.0), max(abs(y - cy) - hy, 0.0)
        d = min(d, math.hypot(dx, dy) if (dx > 0 or dy > 0) else -min(hx - abs(x - cx), hy - abs(y - cy)))
    return d


def main():
    chk = harness.Checker("Isaac project 2: lidar in Isaac Sim + the course's obstacle avoider")
    rclpy.init()
    node = Node("it_isaac_p2")
    clock = ih.SimClock(node)
    state = {"odom": None, "scan": None, "scans": 0}
    node.create_subscription(Odometry, "/odom", lambda m: state.__setitem__("odom", m), 10)

    def on_scan(m):
        state["scan"] = m
        state["scans"] += 1

    node.create_subscription(LaserScan, "/scan", on_scan, 10)

    with ih.isaac(r"isaac\scripts\p2_lidar.py", log_name="isaac_p2"):
        up = harness.wait_until(node, lambda: clock.now is not None and state["odom"] is not None and state["scan"] is not None, timeout=420)
        chk.check(up, "Isaac Sim started and publishes /clock, /odom and /scan")
        if not up:
            chk.finish()
            return chk.failures
        ih.spin_sim_seconds(node, clock, 1.5)
        s = state["scan"]
        n = len(s.ranges)
        print(f"scan: {n} rays, angle {math.degrees(s.angle_min):.1f}..{math.degrees(s.angle_min + n * s.angle_increment):.1f} deg, "
              f"range {s.range_min:.2f}..{s.range_max:.2f} m, frame {s.header.frame_id}", flush=True)
        chk.check(s.header.frame_id == "lidar_link" and n >= 360, f"/scan is a full circle in frame lidar_link ({n} rays)")

        def at(deg):
            i = int(round((math.radians(deg) - s.angle_min) / s.angle_increment)) % n
            return s.ranges[i]

        # The lidar sits 0.08 m ahead of the robot centre; the robot starts at the room centre, facing +x.
        expect = {0: HALF_W - 0.08, 90: HALF_D, 180: HALF_W + 0.08, -90: HALF_D}
        for deg, want in expect.items():
            got = at(deg)
            chk.check(abs(got - want) < 0.12, f"range at {deg:+4d} deg is {got:.2f} m (the wall is {want:.2f} m away)")

        scan_start = list(s.ranges)
        # --- the course's Class 4 node, unchanged
        with harness.process("ros2", "run", "diffbot_navigation", "obstacle_avoider"):
            t_start = clock.now
            xs = []
            worst = [9.9]
            travelled = [0.0]
            last = [None]

            def watch():
                o = state["odom"].pose.pose.position
                if last[0] is not None:
                    travelled[0] += math.hypot(o.x - last[0][0], o.y - last[0][1])
                last[0] = (o.x, o.y)
                worst[0] = min(worst[0], clearance(o.x, o.y))
                xs.append((o.x, o.y))

            ih.spin_sim_seconds(node, clock, 60.0, on_tick=watch, wall_timeout=420)
            print(f"wandered {travelled[0]:.1f} m in {clock.now - t_start:.0f} simulated s; closest approach to an obstacle "
                  f"(robot centre): {worst[0]:.2f} m", flush=True)
        import json
        os.makedirs(ih.ARTIFACTS, exist_ok=True)
        with open(os.path.join(ih.ARTIFACTS, "lidar_run.json"), "w") as f:
            json.dump({"angle_min": s.angle_min, "angle_increment": s.angle_increment, "ranges": [r if math.isfinite(r) else None for r in scan_start], "path": xs[::5]}, f)
        chk.check(travelled[0] > 4.0, f"the avoider drove the robot {travelled[0]:.1f} m in 60 simulated seconds")
        chk.check(worst[0] > ROBOT_RADIUS, f"it never touched anything (centre came within {worst[0]:.2f} m of an obstacle; the robot's own radius is about {ROBOT_RADIUS} m)")
        inside = all(abs(x) < HALF_W and abs(y) < HALF_D for x, y in xs)
        chk.check(inside, "it stayed inside the room")

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
