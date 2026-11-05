"""Computes wheel odometry from /joint_states and broadcasts odom -> base_footprint."""
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster

from diffbot_odometry.odometry_math import update_pose, yaw_to_quaternion


class OdometryNode(Node):
    def __init__(self):
        super().__init__("odometry_node")
        self.declare_parameter("wheel_radius", 0.05)
        self.declare_parameter("wheel_separation", 0.30)
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_footprint")
        self.declare_parameter("publish_tf", True)

        self.radius = self.get_parameter("wheel_radius").value
        self.sep = self.get_parameter("wheel_separation").value
        self.odom_frame = self.get_parameter("odom_frame").value
        self.base_frame = self.get_parameter("base_frame").value
        self.publish_tf = self.get_parameter("publish_tf").value

        self.x = self.y = self.theta = 0.0
        self.prev_left = self.prev_right = None
        self.prev_time = None

        self.odom_pub = self.create_publisher(Odometry, "odom", 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(JointState, "joint_states", self.on_joint_states, 10)

    def on_joint_states(self, msg):
        try:
            left = msg.position[msg.name.index("left_wheel_joint")]
            right = msg.position[msg.name.index("right_wheel_joint")]
        except (ValueError, IndexError):
            return  # message does not carry both wheels
        stamp = rclpy.time.Time.from_msg(msg.header.stamp)

        if self.prev_left is None:  # first sample only primes the state
            self.prev_left, self.prev_right, self.prev_time = left, right, stamp
            return

        d_left = (left - self.prev_left) * self.radius
        d_right = (right - self.prev_right) * self.radius
        dt = (stamp - self.prev_time).nanoseconds / 1e9
        self.prev_left, self.prev_right, self.prev_time = left, right, stamp

        old_theta = self.theta
        self.x, self.y, self.theta = update_pose(self.x, self.y, self.theta, d_left, d_right, self.sep)

        v = (d_left + d_right) / 2.0 / dt if dt > 0 else 0.0
        w = (self.theta - old_theta) / dt if dt > 0 else 0.0
        self.publish(msg.header.stamp, v, w)

    def publish(self, stamp, v, w):
        qx, qy, qz, qw = yaw_to_quaternion(self.theta)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = v
        odom.twist.twist.angular.z = w
        self.odom_pub.publish(odom)

        if self.publish_tf:
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = self.odom_frame
            tf.child_frame_id = self.base_frame
            tf.transform.translation.x = self.x
            tf.transform.translation.y = self.y
            tf.transform.rotation.z = qz
            tf.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(tf)


def main(args=None):
    rclpy.init(args=args)
    node = OdometryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
