"""Project 5 (ROS 2 side): follow a black line on the floor using only the camera image.

Runs in the course's ROS 2 Jazzy environment (not inside Isaac Sim):
    pixi run isaac-line

Subscribes   /camera/image_raw   sensor_msgs/Image (rgb8), the camera looks down at the floor in front of the robot
Publishes    /cmd_vel            geometry_msgs/Twist

    dark pixels = grey value below DARK_FRACTION (70 %) of the picture's typical (median) brightness. A fixed number would not
                  work: the black line is rendered as mid-grey (about 100 of 255) because the light reflects off it.
    error = (mean column of the dark pixels - image centre) / (image width / 2)       -1 .. +1, negative = line on the left
    turn  = -GAIN * error                                                              (positive angular.z turns left)
    drive = SPEED, slowed down in sharp turns; if the line is gone (fewer than MIN_PIXELS dark pixels) the robot stops.
"""
import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Image

DARK_FRACTION = 0.7   # a pixel darker than this share of the median brightness is "line"
GAIN = 1.6            # rad/s of turn per unit of image error
SPEED = 0.12          # m/s
MIN_PIXELS = 30       # fewer dark pixels than this = "I lost the line"
# Why 30: a 5 cm line seen from 0.2 m up is several hundred pixels; a few stray dark pixels (shadow, noise) stay below 30.


def dark_mask(rgb):
    grey = rgb.astype(np.float32).mean(axis=2)
    return grey < DARK_FRACTION * np.median(grey)


def image_to_array(msg):
    """sensor_msgs/Image (rgb8) -> HxWx3 uint8. No cv_bridge needed."""
    return np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)


def steering(mask):
    """(linear, angular, error) from a mask of line pixels; error is None when the line is lost."""
    if mask.sum() < MIN_PIXELS:
        return 0.0, 0.0, None
    half = mask.shape[1] / 2.0
    error = (float(np.nonzero(mask)[1].mean()) - half) / half
    return SPEED * max(0.3, 1.0 - 1.5 * abs(error)), -GAIN * error, error


class LineFollower(Node):
    def __init__(self):
        super().__init__("line_follower")
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(Image, "camera/image_raw", self.on_image, 2)
        self.get_logger().info("waiting for /camera/image_raw ...")

    def on_image(self, msg):
        if msg.encoding != "rgb8":
            self.get_logger().warn(f"expected rgb8, got {msg.encoding}", throttle_duration_sec=5.0)
            return
        mask = dark_mask(image_to_array(msg))
        linear, angular, error = steering(mask)
        cmd = Twist()
        cmd.linear.x, cmd.angular.z = float(linear), float(angular)
        self.cmd_pub.publish(cmd)
        self.get_logger().info("line lost: stopped" if error is None else
                               f"line at {error:+.2f} of the half-width -> v {linear:.2f} m/s, w {angular:+.2f} rad/s",
                               throttle_duration_sec=1.0)


def main(args=None):
    rclpy.init(args=args)
    node = LineFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.cmd_pub.publish(Twist())
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
