"""Headless kinematic simulator that stands in for Gazebo.

Subscribes : /cmd_vel (geometry_msgs/Twist)
Publishes  : /joint_states (wheel positions + velocities), /scan (LaserScan),
             /map (OccupancyGrid, latched), /ground_truth (Odometry in the map frame)
"""
import math
import random
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import Int32

from diffbot_sim import kinematics as kin
from diffbot_sim.world import default_world

LIDAR_X_OFFSET = 0.08  # lidar_joint x in diffbot.urdf.xacro
ROBOT_RADIUS = 0.17


class SimNode(Node):
    def __init__(self):
        super().__init__("diffbot_sim")
        self.declare_parameter("wheel_radius", 0.05)
        self.declare_parameter("wheel_separation", 0.30)
        self.declare_parameter("initial_x", 1.0)
        self.declare_parameter("initial_y", 1.0)
        self.declare_parameter("initial_yaw", 0.0)
        self.declare_parameter("wheel_noise", 0.0)  # random slip: fractional std-dev of each wheel's real speed
        self.declare_parameter("wheel_bias", 0.0)  # systematic error: right wheel really turns this fraction faster
        self.declare_parameter("cmd_timeout", 0.5)
        self.declare_parameter("scan_rate", 10.0)
        self.declare_parameter("scan_samples", 360)
        self.declare_parameter("scan_range_max", 6.0)

        self.radius = self.get_parameter("wheel_radius").value
        self.sep = self.get_parameter("wheel_separation").value
        self.x = self.get_parameter("initial_x").value
        self.y = self.get_parameter("initial_y").value
        self.yaw = self.get_parameter("initial_yaw").value
        self.noise = self.get_parameter("wheel_noise").value
        self.bias = self.get_parameter("wheel_bias").value
        self.cmd_timeout = self.get_parameter("cmd_timeout").value
        self.range_max = self.get_parameter("scan_range_max").value
        n = int(self.get_parameter("scan_samples").value)
        self.scan_angles = np.linspace(-math.pi, math.pi, n, endpoint=False)

        self.world = default_world()
        self.cmd = (0.0, 0.0)
        self.last_cmd_time = time.monotonic()
        self.left_pos = 0.0
        self.right_pos = 0.0
        self.last_step = time.monotonic()
        self.collisions = 0
        self.was_blocked = False

        self.create_subscription(Twist, "cmd_vel", self.on_cmd, 10)
        self.collision_pub = self.create_publisher(Int32, "collision_count", 10)
        self.joint_pub = self.create_publisher(JointState, "joint_states", 10)
        self.scan_pub = self.create_publisher(LaserScan, "scan", 10)
        self.truth_pub = self.create_publisher(Odometry, "ground_truth", 10)
        latched = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.map_pub = self.create_publisher(OccupancyGrid, "map", latched)
        self.publish_map()

        self.create_timer(0.02, self.step)
        self.create_timer(1.0 / self.get_parameter("scan_rate").value, self.publish_scan)
        self.get_logger().info(
            f"DiffBot sim ready at ({self.x:.2f}, {self.y:.2f}, {self.yaw:.2f}) "
            f"noise={self.noise} bias={self.bias}"
        )

    # --- callbacks -------------------------------------------------------
    def on_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)
        self.last_cmd_time = time.monotonic()

    def step(self):
        now = time.monotonic()
        dt = min(now - self.last_step, 0.1)
        self.last_step = now
        v, w = self.cmd
        if now - self.last_cmd_time > self.cmd_timeout:
            v, w = 0.0, 0.0  # watchdog: stop when commands stop arriving

        cmd_left, cmd_right = kin.wheel_speeds(v, w, self.radius, self.sep)
        jitter_l = random.gauss(0.0, self.noise) if self.noise > 0.0 else 0.0
        jitter_r = random.gauss(0.0, self.noise) if self.noise > 0.0 else 0.0
        # The robot REALLY moves with slipped wheel speeds, but the encoders (joint_states) below report the
        # commanded rotation. That mismatch is what makes wheel odometry drift.
        left, right = kin.slipped_wheel_speeds(cmd_left, cmd_right, self.bias, jitter_l, jitter_r)
        true_v, true_w = kin.body_twist(left, right, self.radius, self.sep)

        nx, ny, nth = kin.step_pose(self.x, self.y, self.yaw, true_v, true_w, dt)
        blocked = self.world.circle_collides(nx, ny, ROBOT_RADIUS)
        if blocked:
            # Contact: slide along the obstacle if one axis is free, otherwise stay put.
            # Heading still changes. Wheels keep spinning as commanded (they slip), so wheel
            # odometry drifts after a collision, just like on a real robot.
            if not self.world.circle_collides(nx, self.y, ROBOT_RADIUS):
                ny = self.y
            elif not self.world.circle_collides(self.x, ny, ROBOT_RADIUS):
                nx = self.x
            else:
                nx, ny = self.x, self.y
            if not self.was_blocked:  # count each new impact once
                self.collisions += 1
                self.collision_pub.publish(Int32(data=self.collisions))
                self.get_logger().warn(f"Collision #{self.collisions} at ({nx:.2f}, {ny:.2f})")
        self.was_blocked = blocked
        self.x, self.y, self.yaw = nx, ny, nth

        self.left_pos += cmd_left * dt  # encoders: ideal, commanded rotation
        self.right_pos += cmd_right * dt
        self.publish_joint_states(cmd_left, cmd_right)
        self.publish_truth(true_v, true_w)

    # --- publishers ------------------------------------------------------
    def publish_joint_states(self, left_vel, right_vel):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ["left_wheel_joint", "right_wheel_joint"]
        msg.position = [self.left_pos, self.right_pos]
        msg.velocity = [left_vel, right_vel]
        self.joint_pub.publish(msg)

    def publish_truth(self, v, w):
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.child_frame_id = "base_footprint"
        msg.pose.pose.position.x = self.x
        msg.pose.pose.position.y = self.y
        qx, qy, qz, qw = kin.yaw_to_quaternion(self.yaw)
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        msg.twist.twist.linear.x = v
        msg.twist.twist.angular.z = w
        self.truth_pub.publish(msg)

    def publish_scan(self):
        ox = self.x + LIDAR_X_OFFSET * math.cos(self.yaw)
        oy = self.y + LIDAR_X_OFFSET * math.sin(self.yaw)
        ranges = self.world.raycast(ox, oy, self.scan_angles + self.yaw, self.range_max)
        msg = LaserScan()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "lidar_link"
        msg.angle_min = float(self.scan_angles[0])
        msg.angle_max = float(self.scan_angles[-1])
        msg.angle_increment = float(self.scan_angles[1] - self.scan_angles[0])
        msg.range_min = 0.12
        msg.range_max = float(self.range_max)
        msg.ranges = [float(r) for r in ranges]
        self.scan_pub.publish(msg)

    def publish_map(self):
        msg = OccupancyGrid()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.info.resolution = self.world.resolution
        msg.info.width = self.world.cols
        msg.info.height = self.world.rows
        msg.info.origin.orientation.w = 1.0
        msg.data = self.world.to_occupancy_data()
        self.map_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
