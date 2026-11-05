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

        d_left = (left - self.prev_left) * WHEEL_RADIUS
        d_right = (right - self.prev_right) * WHEEL_RADIUS
        self.prev_left, self.prev_right = left, right

        ds = (d_left + d_right) / 2.0
        dtheta = (d_right - d_left) / WHEEL_SEPARATION

        self.x += ds * math.cos(self.theta + dtheta / 2.0)
        self.y += ds * math.sin(self.theta + dtheta / 2.0)
        self.theta += dtheta

        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_footprint"
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.theta / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.theta / 2.0)
        self.pub.publish(odom)


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
