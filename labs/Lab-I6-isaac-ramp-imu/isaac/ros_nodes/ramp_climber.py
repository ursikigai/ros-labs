"""Project 6 (ROS 2 side): drive up the ramp, read the slope from the IMU, stop on the flat deck.

Runs in the course's ROS 2 Jazzy environment (not inside Isaac Sim):
    pixi run isaac-ramp

Subscribes   /imu      sensor_msgs/Imu   (orientation = how the body is tilted)
Publishes    /cmd_vel  geometry_msgs/Twist

A level robot reads pitch 0. Pitch is the rotation about the robot's y axis; in ROS (REP 103) a positive pitch tips the NOSE DOWN,
so a robot climbing a ramp has a negative pitch. We print slope = -pitch ("nose up" is positive):

    waiting   -> drive; when the slope exceeds CLIMB_DEG                       -> climbing
    climbing  -> keep driving; when the slope has been below LEVEL_DEG for 1 s -> on the deck: stop
    any state -> if the slope is steeper than TOO_STEEP_DEG: stop (and stay stopped)

Time is taken from the IMU's own timestamps (simulated time), never from the wall clock.
"""
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Imu

SPEED = 0.2            # m/s
CLIMB_DEG = 5.0        # slope above this = "I am on the ramp"
LEVEL_DEG = 2.0        # slope below this (after climbing) = "level again"
LEVEL_SECONDS = 1.0
TOO_STEEP_DEG = 25.0


def pitch_of(q):
    """Pitch in radians (positive = nose down): the standard ZYX formula."""
    return math.asin(max(-1.0, min(1.0, 2 * (q.w * q.y - q.z * q.x))))


def slope_deg(q):
    return -math.degrees(pitch_of(q))


class RampClimber(Node):
    def __init__(self):
        super().__init__("ramp_climber")
        self.state = "waiting"
        self.level_since = None
        self.max_slope = 0.0
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(Imu, "imu", self.on_imu, 10)
        self.get_logger().info("waiting for /imu ...")

    def on_imu(self, msg):
        slope = slope_deg(msg.orientation)
        now = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.max_slope = max(self.max_slope, slope)
        if self.state in ("waiting", "climbing") and slope > TOO_STEEP_DEG:
            self.state = "too steep"
        elif self.state == "waiting" and slope > CLIMB_DEG:
            self.state = "climbing"
            self.get_logger().info(f"on the ramp: slope {slope:.1f} degrees")
        elif self.state == "climbing":
            if slope < LEVEL_DEG:
                self.level_since = self.level_since if self.level_since is not None else now
                if now - self.level_since >= LEVEL_SECONDS:
                    self.state = "on the deck"
                    self.get_logger().info(f"on the deck: level again (steepest slope was {self.max_slope:.1f} degrees)")
            else:
                self.level_since = None
        cmd = Twist()
        if self.state in ("waiting", "climbing"):
            cmd.linear.x = SPEED
        self.cmd_pub.publish(cmd)
        self.get_logger().info(f"{self.state}: slope {slope:+.1f} degrees", throttle_duration_sec=1.0)


def main(args=None):
    rclpy.init(args=args)
    node = RampClimber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.cmd_pub.publish(Twist())
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
