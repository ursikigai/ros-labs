"""End-to-end test of Isaac project 5: a downward camera in Isaac Sim and a ROS 2 node that follows a black line.

Checks the picture first (is the line there, is it dark on pale?), then runs isaac/ros_nodes/line_follower.py and measures,
from /odom, how far from the line the robot drove.
"""
import json
import math
import os
import sys

import isaac_harness as ih
import harness
import numpy as np
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Image

sys.path.insert(0, os.path.join(ih.ROOT, "isaac", "scripts"))
import line_track as lt  # noqa: E402  (plain maths, shared with p5_line.py)

FOLLOWER = os.path.join(ih.ROOT, "isaac", "ros_nodes", "line_follower.py")


def main():
    chk = harness.Checker("Isaac project 5: downward camera + a ROS 2 node that follows a line")
    sys.path.insert(0, os.path.dirname(FOLLOWER))
    import line_follower as lf

    rclpy.init()
    node = Node("it_isaac_p5")
    clock = ih.SimClock(node)
    st = {"odom": None, "rgb": None}
    trace = []   # (sim time, x, y)

    def on_odom(m):
        st["odom"] = m
        if clock.now is not None:
            trace.append((clock.now, m.pose.pose.position.x, m.pose.pose.position.y))

    node.create_subscription(Odometry, "/odom", on_odom, 10)
    node.create_subscription(Image, "/camera/image_raw", lambda m: st.__setitem__("rgb", m), 2)

    with ih.isaac(r"isaac\scripts\p5_line.py", log_name="isaac_p5"):
        up = harness.wait_until(node, lambda: st["odom"] is not None and st["rgb"] is not None and clock.now is not None, timeout=480)
        chk.check(up, "Isaac Sim started and publishes /clock, /odom and /camera/image_raw")
        if not up:
            chk.finish()
            return chk.failures
        ih.spin_sim_seconds(node, clock, 1.5)
        rgb = st["rgb"]
        img = lf.image_to_array(rgb)
        chk.check(rgb.encoding == "rgb8" and (rgb.width, rgb.height) == (160, 120), f"/camera/image_raw is 160x120 rgb8 ({rgb.width}x{rgb.height} {rgb.encoding})")
        ih.save_png(os.path.join(ih.ARTIFACTS, "line_start.png"), img)
        mask = lf.dark_mask(img)
        cols = np.nonzero(mask)[1]
        bright = float(np.median(img[~mask])) if (~mask).any() else 0.0
        print(f"dark pixels: {mask.sum()} of {mask.size}, mean column {cols.mean() if cols.size else float('nan'):.0f} of {rgb.width}; "
              f"median of the other pixels {bright:.0f}", flush=True)
        chk.check(150 <= mask.sum() <= 3500, f"the black line is visible, and nothing else dark (the robot's own body is not in the picture): {mask.sum()} dark pixels")
        chk.check(cols.size > 0 and abs(cols.mean() - rgb.width / 2) < 20, "...and near the middle of the picture (the robot stands on it)")
        chk.check(bright > 150, f"the floor around it is pale (median {bright:.0f} of 255)")
        steer = lf.steering(mask)
        chk.check(steer[0] > 0.05 and abs(steer[1]) < 0.4, f"the follower's rule says: drive on, hardly turn (v {steer[0]:.2f}, w {steer[1]:+.2f})")

        start = clock.now
        n0 = len(trace)
        import time

        with harness.process(sys.executable, FOLLOWER):
            wall0 = time.monotonic()
            while clock.now - start < 90 and time.monotonic() - wall0 < 480:
                rclpy.spin_once(node, timeout_sec=0.05)
                if len(trace) > n0 + 100 and trace[-1][1] > lt.X_END - 0.1:
                    break
            ih.spin_sim_seconds(node, clock, 3.0)   # let it settle / stop
        run = trace[n0:]
        errs = [lt.distance_to_line(x, y) for _, x, y in run]
        t_end, x, y = run[-1]
        end_move = math.hypot(run[-1][1] - [r for r in run if r[0] > t_end - 2.0][0][1], run[-1][2] - [r for r in run if r[0] > t_end - 2.0][0][2])
        print(f"drove {t_end - start:.0f} simulated s; final x={x:.2f} y={y:.2f}; distance from the line: mean {np.mean(errs) * 100:.1f} cm, "
              f"max {max(errs) * 100:.1f} cm; moved {end_move * 100:.1f} cm in the last 2 s", flush=True)
        ih.save_png(os.path.join(ih.ARTIFACTS, "line_end.png"), lf.image_to_array(st["rgb"]))
        chk.check(x > 3.0, f"it followed the line to its far end (x = {x:.2f} m; the line ends at {lt.X_END} m)")
        chk.check(abs(y - lt.BEND_SIDE) < 0.15, f"...after the 0.6 m bend to the left (y = {y:.2f} m)")
        chk.check(np.mean(errs) < 0.06, f"on average it stayed {np.mean(errs) * 100:.1f} cm from the line (limit 6 cm)")
        chk.check(max(errs) < 0.18, f"at worst it was {max(errs) * 100:.1f} cm from the line (limit 18 cm)")
        chk.check(end_move < 0.03, f"it stopped at the end of the line (moved {end_move * 100:.1f} cm in the last 2 s)")
        with open(os.path.join(ih.ARTIFACTS, "line_run.json"), "w") as f:   # for the run book's figure
            json.dump({"trace": [(round(t - start, 2), round(x, 3), round(y, 3)) for t, x, y in run[::4]], "errors_cm": [round(e * 100, 2) for e in errs[::4]]}, f)

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
