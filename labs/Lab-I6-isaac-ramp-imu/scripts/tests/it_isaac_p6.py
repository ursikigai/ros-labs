"""End-to-end test of Isaac project 6: an IMU in Isaac Sim, and a ROS 2 node that climbs a ramp using the slope it reads.

Checks /imu while the robot stands still on level ground (gravity must read +9.81 m/s^2 on z, no tilt), then runs
isaac/ros_nodes/ramp_climber.py and compares the steepest slope the IMU reported with the ramp's real angle (10 degrees).
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
from sensor_msgs.msg import Imu

RAMP_ANGLE, RAMP_START, RAMP_RUN, DECK = 10.0, 0.8, 2.0, 1.0     # same as p6_ramp.py
DECK_HEIGHT = RAMP_RUN * math.tan(math.radians(RAMP_ANGLE))      # 0.353 m
NODE = os.path.join(ih.ROOT, "isaac", "ros_nodes", "ramp_climber.py")


def main():
    chk = harness.Checker("Isaac project 6: IMU + a 10 degree ramp")
    sys.path.insert(0, os.path.dirname(NODE))
    import ramp_climber as rc

    rclpy.init()
    node = Node("it_isaac_p6")
    clock = ih.SimClock(node)
    st = {"odom": None, "imu": None}
    imus = []    # (sim time, slope degrees, |acc|)
    odoms = []   # (sim time, x, z)

    def on_imu(m):
        st["imu"] = m
        a = m.linear_acceleration
        if clock.now is not None:
            imus.append((clock.now, rc.slope_deg(m.orientation), math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2)))

    def on_odom(m):
        st["odom"] = m
        if clock.now is not None:
            odoms.append((clock.now, m.pose.pose.position.x, m.pose.pose.position.z))

    node.create_subscription(Imu, "/imu", on_imu, 10)
    node.create_subscription(Odometry, "/odom", on_odom, 10)

    with ih.isaac(r"isaac\scripts\p6_ramp.py", log_name="isaac_p6"):
        up = harness.wait_until(node, lambda: st["odom"] is not None and st["imu"] is not None and clock.now is not None, timeout=480)
        chk.check(up, "Isaac Sim started and publishes /clock, /odom and /imu")
        if not up:
            chk.finish()
            return chk.failures
        ih.spin_sim_seconds(node, clock, 2.0)
        m = st["imu"]
        a = m.linear_acceleration
        mag = math.sqrt(a.x ** 2 + a.y ** 2 + a.z ** 2)
        print(f"standing still: frame {m.header.frame_id!r}, acceleration ({a.x:.2f}, {a.y:.2f}, {a.z:.2f}) |a|={mag:.2f}, "
              f"slope {rc.slope_deg(m.orientation):+.2f} deg", flush=True)
        chk.check(m.header.frame_id == "base_link", f"/imu is stamped with frame base_link ({m.header.frame_id})")
        chk.check(abs(mag - 9.81) < 0.8, f"at rest the acceleration has the size of gravity ({mag:.2f} m/s^2, expected 9.81)")
        chk.check(a.z > 8.5, f"...and points up the robot's own z axis (z = {a.z:+.2f})")
        chk.check(abs(rc.slope_deg(m.orientation)) < 2.5, f"on level ground the IMU reports no tilt ({rc.slope_deg(m.orientation):+.2f} deg)")
        z0 = odoms[-1][2]

        start = clock.now
        n_imu0 = len(imus)
        import time

        with harness.process(sys.executable, NODE):
            wall0 = time.monotonic()
            while clock.now - start < 90 and time.monotonic() - wall0 < 480:
                rclpy.spin_once(node, timeout_sec=0.05)
                if odoms[-1][1] > RAMP_START + RAMP_RUN + 0.2:      # on the deck: give the node time to see "level" and stop
                    break
            ih.spin_sim_seconds(node, clock, 4.0)
        run = imus[n_imu0:]
        steepest = max(s for _, s, _ in run)
        t, x, z = odoms[-1]
        tail = [o for o in odoms if o[0] > t - 2.0]
        end_move = abs(tail[-1][1] - tail[0][1])
        final_slope = sum(s for tt, s, _ in run if tt > run[-1][0] - 1.0) / max(1, len([1 for tt, s, _ in run if tt > run[-1][0] - 1.0]))
        print(f"steepest slope {steepest:.1f} deg (ramp: {RAMP_ANGLE}); final x={x:.2f} m, height gain {z - z0:.2f} m (deck: {DECK_HEIGHT:.2f}); "
              f"final slope {final_slope:+.1f}; moved {end_move * 100:.1f} cm in the last 2 s", flush=True)
        chk.check(RAMP_ANGLE - 4 < steepest < RAMP_ANGLE + 4, f"on the ramp the IMU measured a slope of {steepest:.1f} degrees (the ramp has {RAMP_ANGLE})")
        chk.check(x > RAMP_START + RAMP_RUN + 0.05, f"the robot got up onto the deck (x = {x:.2f} m, the deck starts at {RAMP_START + RAMP_RUN} m)")
        chk.check(abs((z - z0) - DECK_HEIGHT) < 0.1, f"/odom shows it climbed {z - z0:.2f} m (the deck is {DECK_HEIGHT:.2f} m high)")
        chk.check(abs(final_slope) < 3.0, f"on the deck the IMU reads level again ({final_slope:+.1f} deg)")
        chk.check(end_move < 0.03, f"the node stopped the robot on the deck (moved {end_move * 100:.1f} cm in the last 2 s)")
        chk.check(x < RAMP_START + RAMP_RUN + DECK, f"...before the end of the deck (x = {x:.2f} m < {RAMP_START + RAMP_RUN + DECK} m)")
        with open(os.path.join(ih.ARTIFACTS, "ramp_run.json"), "w") as f:   # for the run book's figure
            json.dump({"imu": [(round(tt - start, 2), round(s, 2)) for tt, s, _ in run[::6]],
                       "odom": [(round(tt - start, 2), round(xx, 3), round(zz - z0, 3)) for tt, xx, zz in odoms if tt >= start][::4]}, f)

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
