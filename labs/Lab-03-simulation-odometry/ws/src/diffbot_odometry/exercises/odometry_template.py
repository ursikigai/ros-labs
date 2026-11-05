"""STUDENT EXERCISE (Class 3): complete the TODOs, then run it instead of odometry_node.

Adapted from upstream/robotics_essentials_ros2 exercise 4 (Henki Robotics), reworked to
use wheel *positions* (more accurate than integrating velocities) and the DiffBot frames.

Run (with the simulator already running):
    pixi run python ws/src/diffbot_odometry/exercises/odometry_template.py
Check it:
    pixi run ros2 topic echo /my_odom --once --no-daemon
"""
import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import JointState

WHEEL_RADIUS = 0.05
WHEEL_SEPARATION = 0.30


class MyOdometry(Node):
    def __init__(self):
        super().__init__("my_odometry")
        self.x = self.y = self.theta = 0.0
        self.prev_left = self.prev_right = None
        self.pub = self.create_publisher(Odometry, "my_odom", 10)
        self.create_subscription(JointState, "joint_states", self.on_joint_states, 10)

    def on_joint_states(self, msg):
        left = msg.position[msg.name.index("left_wheel_joint")]
        right = msg.position[msg.name.index("right_wheel_joint")]
        if self.prev_left is None:
            self.prev_left, self.prev_right = left, right
            return

        # TODO 1: how far (in metres) did each wheel travel since the last message?
        #         hint: change in wheel angle [rad] * WHEEL_RADIUS
        d_left = 0.0
        d_right = 0.0
        self.prev_left, self.prev_right = left, right

        # TODO 2: distance travelled by the robot centre, and the change in heading.
        #         hint: ds = average of both wheels; dtheta = (d_right - d_left) / separation
        ds = 0.0
        dtheta = 0.0

        # TODO 3: update self.x, self.y, self.theta.
        #         hint: use the heading halfway through the step, theta + dtheta / 2
        _ = math.cos  # remove once you use math

        # TODO 4: fill an Odometry message (frame_id "odom", child "base_footprint"),
        #         convert theta to a quaternion (z = sin(theta/2), w = cos(theta/2)), publish it.


def main():
    rclpy.init()
    node = MyOdometry()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
