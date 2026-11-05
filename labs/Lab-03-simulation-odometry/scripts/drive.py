"""Publish a constant velocity on /cmd_vel for a while, then stop.

Usage:  pixi run drive <linear m/s> <angular rad/s> <seconds>
        pixi run drive 0.2 0.0 4      # forward 0.8 m
        pixi run drive 0.0 0.5 3      # turn left 1.5 rad
Needs a simulator running (Classes 3-5). The simulator itself also stops the robot 0.5 s after
the last command, so this script must keep publishing; that is why it loops at 20 Hz.
"""
import sys
import time

import rclpy
from geometry_msgs.msg import Twist, Vector3


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    v, w, seconds = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])

    rclpy.init()
    node = rclpy.create_node("drive")
    pub = node.create_publisher(Twist, "cmd_vel", 10)
    # ROS discovery takes a second or two on Windows; messages published before the simulator is connected
    # are lost, which would silently shorten the drive. Wait until someone is listening.
    wait_end = time.monotonic() + 20.0
    while pub.get_subscription_count() == 0 and time.monotonic() < wait_end:
        time.sleep(0.1)
    if pub.get_subscription_count() == 0:
        print("FAILED: nothing is listening on /cmd_vel. Is a simulator running (pixi run demo-sim)?")
        return 1
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pub.publish(Twist(linear=Vector3(x=v), angular=Vector3(z=w)))
        time.sleep(0.05)
    pub.publish(Twist())  # explicit stop
    time.sleep(0.1)
    print(f"drove v={v} m/s, w={w} rad/s for {seconds} s")
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
