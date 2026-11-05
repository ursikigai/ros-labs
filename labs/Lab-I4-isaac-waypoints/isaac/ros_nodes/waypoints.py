"""Project 4 (ROS 2 side): drive to the red, green and blue square, in that order, using only /odom.

Runs in the course's ROS 2 Jazzy environment (not inside Isaac Sim):
    pixi run isaac-waypoints

Subscribes   /odom     nav_msgs/Odometry
Publishes    /cmd_vel  geometry_msgs/Twist

The rule is the same as in Class 5's "go to a point", only much smaller:
    heading_error = direction_to_goal - my_heading          (wrapped to -180..+180 degrees)
    turn  = GAIN * heading_error                            (a proportional controller)
    drive = only when roughly facing the goal, slower when close
When the goal is closer than TOLERANCE the next one starts; after the last one the robot stops.
"""
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

# (name, x, y) in metres, in the odom frame (the robot starts at 0, 0 looking along +x). Keep in step with p4_waypoints.py.
WAYPOINTS = [("A (red)", 1.5, 0.0), ("B (green)", 1.5, 1.5), ("C (blue)", -0.5, 1.5)]
TOLERANCE = 0.12      # metres: closer than this counts as "arrived"
GAIN = 1.5            # rad/s of turn per radian of heading error
MAX_TURN = 1.0        # rad/s
MAX_SPEED = 0.25      # m/s
FACING = 0.5          # radians: drive only when the goal is within this angle of straight ahead


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def command(x, y, yaw, goal):
    """(linear, angular, distance) that steer a robot at (x, y, yaw) towards goal=(gx, gy)."""
    dx, dy = goal[0] - x, goal[1] - y
    dist = math.hypot(dx, dy)
    error = wrap(math.atan2(dy, dx) - yaw)
    angular = max(-MAX_TURN, min(MAX_TURN, GAIN * error))
    linear = 0.0
    if abs(error) < FACING:
        linear = min(MAX_SPEED, 0.6 * dist + 0.04) * math.cos(error)
    return linear, angular, dist


class Waypoints(Node):
    def __init__(self):
        super().__init__("waypoints")
        self.index = 0
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(Odometry, "odom", self.on_odom, 10)
        self.get_logger().info(f"{len(WAYPOINTS)} waypoints; first goal: {WAYPOINTS[0][0]}")

    def on_odom(self, msg):
        cmd = Twist()
        if self.index < len(WAYPOINTS):
            p = msg.pose.pose.position
            name, gx, gy = WAYPOINTS[self.index]
            cmd.linear.x, cmd.angular.z, dist = command(p.x, p.y, yaw_of(msg.pose.pose.orientation), (gx, gy))
            if dist < TOLERANCE:
                self.get_logger().info(f"arrived at {name}  (x {p.x:.2f}, y {p.y:.2f})")
                self.index += 1
                cmd = Twist()
                if self.index == len(WAYPOINTS):
                    self.get_logger().info("all waypoints visited: stopping")
            else:
                self.get_logger().info(f"-> {name}: {dist:.2f} m to go", throttle_duration_sec=1.5)
        self.cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = Waypoints()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.cmd_pub.publish(Twist())
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
