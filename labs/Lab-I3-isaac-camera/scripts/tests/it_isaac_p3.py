"""End-to-end test of Isaac project 3: a camera in Isaac Sim and a ROS 2 node that steers by colour.

Checks the camera topics, then starts isaac/ros_nodes/color_follower.py (the node a student runs with `pixi run isaac-follower`)
and watches the robot turn towards the red cube and stop in front of it. Needs the NVIDIA GPU (ray-traced camera images).
"""
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

CUBE = (2.2, 1.3)       # centre of the red cube (see p3_camera.py)
DECOY = (2.2, -1.2)
CUBE_HALF = 0.15
CAMERA_AHEAD = 0.12     # camera is this far in front of the robot centre
FOLLOWER = os.path.join(ih.ROOT, "isaac", "ros_nodes", "color_follower.py")


def main():
    chk = harness.Checker("Isaac project 3: camera in Isaac Sim + a ROS 2 node that steers by colour")
    sys.path.insert(0, os.path.dirname(FOLLOWER))
    import color_follower as cf

    rclpy.init()
    node = Node("it_isaac_p3")
    clock = ih.SimClock(node)
    st = {"odom": None, "rgb": None, "depth": None}
    node.create_subscription(Odometry, "/odom", lambda m: st.__setitem__("odom", m), 10)
    node.create_subscription(Image, "/camera/image_raw", lambda m: st.__setitem__("rgb", m), 2)
    node.create_subscription(Image, "/camera/depth", lambda m: st.__setitem__("depth", m), 2)

    with ih.isaac(r"isaac\scripts\p3_camera.py", log_name="isaac_p3"):
        up = harness.wait_until(node, lambda: all(st[k] is not None for k in ("odom", "rgb", "depth")) and clock.now is not None, timeout=480)
        chk.check(up, "Isaac Sim started and publishes /clock, /odom, /camera/image_raw and /camera/depth")
        if not up:
            chk.finish()
            return chk.failures
        ih.spin_sim_seconds(node, clock, 1.5)
        rgb, dep = st["rgb"], st["depth"]
        print(f"image: {rgb.width}x{rgb.height} {rgb.encoding}; depth: {dep.width}x{dep.height} {dep.encoding}", flush=True)
        chk.check(rgb.encoding == "rgb8" and (rgb.width, rgb.height) == (320, 240), f"/camera/image_raw is 320x240 rgb8 ({rgb.width}x{rgb.height} {rgb.encoding})")
        chk.check(dep.encoding == "32FC1" and (dep.width, dep.height) == (320, 240), f"/camera/depth is 320x240 32FC1 ({dep.width}x{dep.height} {dep.encoding})")
        img = cf.image_to_array(rgb)
        chk.check(img.mean() > 8, f"the image is not black (mean pixel value {img.mean():.0f})")

        ih.save_png(os.path.join(ih.ARTIFACTS, "camera_start.png"), img)
        mask = cf.red_mask(img)
        cols = np.nonzero(mask)[1]
        print(f"red pixels: {mask.sum()}, mean column {cols.mean() if cols.size else float('nan'):.0f} of {rgb.width}", flush=True)
        chk.check(mask.sum() >= 40, f"the red cube is visible from the start ({mask.sum()} red pixels)")
        chk.check(cols.size > 0 and cols.mean() < rgb.width / 2 - 20, "...on the LEFT of the picture (the cube is 31 degrees to the left)")
        green = (img[..., 1].astype(int) - img[..., 0] > 60) & (img[..., 1].astype(int) - img[..., 2] > 60)
        gcols = np.nonzero(green)[1]
        chk.check(gcols.size > 20 and gcols.mean() > rgb.width / 2, f"the green decoy is visible on the RIGHT ({green.sum()} green pixels)")

        # --- the student's node
        o = st["odom"].pose.pose.position
        y0 = ih.yaw_of(st["odom"].pose.pose.orientation)
        with harness.process(sys.executable, FOLLOWER):
            ih.spin_sim_seconds(node, clock, 60.0, wall_timeout=420)
        pos = st["odom"].pose.pose
        x, y, yaw = pos.position.x, pos.position.y, ih.yaw_of(pos.orientation)
        dist = math.hypot(CUBE[0] - x, CUBE[1] - y)
        bearing = ih.wrap(math.atan2(CUBE[1] - y, CUBE[0] - x) - yaw)
        dist_decoy = math.hypot(DECOY[0] - x, DECOY[1] - y)
        print(f"final pose x={x:.2f} y={y:.2f} yaw={math.degrees(yaw):.0f} deg; cube {dist:.2f} m away, {math.degrees(bearing):+.0f} deg off the nose", flush=True)
        chk.check(abs(ih.wrap(yaw - y0)) > 0.3, f"the robot turned towards the cube (heading changed {math.degrees(ih.wrap(yaw - y0)):+.0f} deg)")
        chk.check(abs(bearing) < math.radians(12), f"it points at the cube (within {math.degrees(abs(bearing)):.0f} deg)")
        want = cf.STOP_DISTANCE + CAMERA_AHEAD + CUBE_HALF
        chk.check(abs(dist - want) < 0.25, f"it stopped {dist:.2f} m from the cube centre (about {want:.2f} m expected)")
        chk.check(dist < dist_decoy, "...and it went for the red cube, not the green decoy")

        ih.save_png(os.path.join(ih.ARTIFACTS, "camera_end.png"), cf.image_to_array(st["rgb"]))
        # --- depth camera cross-check: straight ahead is the cube's front face
        harness.wait_until(node, lambda: st["depth"] is not None, timeout=10)
        d = np.frombuffer(st["depth"].data, dtype=np.float32).reshape(st["depth"].height, st["depth"].width)
        centre = float(np.median(d[110:130, 150:170]))
        expect = dist - CAMERA_AHEAD - CUBE_HALF
        print(f"depth at the image centre {centre:.2f} m; geometry says {expect:.2f} m", flush=True)
        chk.check(abs(centre - expect) < 0.15, f"/camera/depth agrees with the geometry ({centre:.2f} m measured, {expect:.2f} m expected)")

    node.destroy_node()
    rclpy.shutdown()
    chk.finish()
    return chk.failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)