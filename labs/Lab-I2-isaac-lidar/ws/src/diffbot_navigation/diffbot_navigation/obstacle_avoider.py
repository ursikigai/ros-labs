"""Class 4: LaserScan in, cmd_vel out. Wanders while avoiding obstacles."""
import rclpy
from geometry_msgs.msg import Twist, Vector3
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

from diffbot_navigation import reactive


class ObstacleAvoider(Node):
    def __init__(self):
        super().__init__("obstacle_avoider")
        self.turn_dir = 0
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(LaserScan, "scan", self.on_scan, 10)

    def on_scan(self, scan):
        v, w, self.turn_dir = reactive.compute_command(
            list(scan.ranges), scan.angle_min, scan.angle_increment, self.turn_dir
        )
        self.cmd_pub.publish(Twist(linear=Vector3(x=float(v)), angular=Vector3(z=float(w))))


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoider()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
