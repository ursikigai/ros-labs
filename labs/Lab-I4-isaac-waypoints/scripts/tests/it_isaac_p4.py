"""End-to-end test of Isaac project 4: a ROS 2 node drives DiffBot to three squares on the floor, in order.

Starts Isaac Sim (p4_waypoints.py), then isaac/ros_nodes/waypoints.py (the node a student runs with `pixi run isaac-waypoints`)
and judges the result ONLY from /odom, which Isaac Sim publishes: how close the robot came to each square and in which order.
"""
import json
import math
import os
import sys

import isaac_harness as ih
import harness
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node

SQUARES = [("A (red)", 1.5, 0.0), ("B (green)", 1.5, 1.5), ("C (blue)", -0.5, 1.5)]   # same as p4_waypoints.py
NODE = os.path.join(ih.ROOT, "isaac", "ros_nodes", "waypoints.py")


def main():
    chk = harness.Checker("Isaac project 4: waypoints (ROS 2 node + odometry from Isaac Sim)")
    rclpy.init()
    node = Node("it_isaac_p4")
    clock = ih.SimClock(node)
    trace = []   # (sim time, x, y)
    st = {"odom": None}

    def on_odom(m):
        st["odom"] = m
        if clock.now is not None:
            trace.append((clock.now, m.pose.pose.position.x, m.pose.pose.position.y))

    node.create_subscription(Odometry, "/odom", on_odom, 10)

    with ih.isaac(r"isaac\scripts\p4_waypoints.py", log_name="isaac_p4"):
        up = harness.wait_until(node, lambda: st["odom"] is not None and clock.now is not None, timeout=480)
        chk.check(up, "Isaac Sim started and publishes /clock and /odom")
        if not up:
            chk.finish()
            return chk.failures
        ih.spin_sim_seconds(node, clock, 1.0)
        p = st["odom"].pose.pose.position
        chk.check(math.hypot(p.x, p.y) < 0.1, f"the robot starts at the origin ({p.x:.2f}, {p.y:.2f})")

        reached = {}   # name -> sim time of the first time the robot was within 0.2 m of the square centre
        start = clock.now
        with harness.process(sys.executable, NODE):
            import time

            wall0 = time.monotonic()
            done_at = None
            while clock.now - start < 150 and time.monotonic() - wall0 < 480:
                rclpy.spin_once(node, timeout_sec=0.05)
                if trace:
                    t, x, y = trace[-1]
                    for name, gx, gy in SQUARES:
                        if name not in reached and math.hypot(gx - x, gy - y) < 0.2:
                            reached[name] = t - start
                            print(f"reached {name} after {t - start:.1f} simulated s (x {x:.2f}, y {y:.2f})", flush=True)
                    if len(reached) == len(SQUARES) and done_at is None:
                        done_at = t
                    if done_at is not None and t - done_at > 3.0:
                        break

        chk.check(len(reached) == len(SQUARES), f"the robot came within 20 cm of all three squares ({len(reached)} of 3)")
        times = [reached.get(n) for n, _, _ in SQUARES]
        in_order = all(t is not None for t in times) and times == sorted(times)
        chk.check(in_order, "...in the order A, B, C" + (f" (after {times[0]:.0f}, {times[1]:.0f}, {times[2]:.0f} simulated s)" if in_order else ""))

        # it must STOP at the end: the last 2 simulated seconds of the trace hardly move
        t_end = trace[-1][0]
        tail = [(x, y) for t, x, y in trace if t > t_end - 2.0]
        moved = math.hypot(tail[-1][0] - tail[0][0], tail[-1][1] - tail[0][1]) if len(tail) > 1 else 99.0
        _, x, y = trace[-1]
        gx, gy = SQUARES[-1][1:]
        print(f"final position x={x:.2f} y={y:.2f}; moved {moved * 100:.1f} cm in the last 2 s", flush=True)
        chk.check(moved < 0.03, f"it stopped after the last square (moved {moved * 100:.1f} cm in the last 2 s)")
        chk.check(math.hypot(gx - x, gy - y) < 0.2, f"...and it stands on square C ({math.hypot(gx - x, gy - y) * 100:.0f} cm from its centre)")
        chk.check(all(abs(v) < 4.0 for _, a, b in trace for v in (a, b)), "it never left the 8 x 6 m room")
        with open(os.path.join(ih.ARTIFACTS, "waypoints_run.json"), "w") as f:   # for the run book's figure
            json.dump({"squares": SQUARES, "reached": reached, "trace": [(round(t - start, 2), round(x, 3), round(y, 3)) for t, x, y in trace[::4] if t >= start]}, f)

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
