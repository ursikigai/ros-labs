"""Project 3 (ROS 2 side): steer towards the red cube using only the camera image.

Runs in the course's ROS 2 Jazzy environment (not inside Isaac Sim):
    pixi run isaac-follower

Subscribes   /camera/image_raw   sensor_msgs/Image (rgb8)
             /camera/depth       sensor_msgs/Image (32FC1, metres)   used only to stop in front of the cube
Publishes    /cmd_vel            geometry_msgs/Twist

The logic is a proportional controller on the horizontal position of the red pixels:
    error = (centroid_x - image_centre_x) / (image_width / 2)          -1 .. +1, negative = target to the left
    turn  = -GAIN * error                                              (positive angular.z turns left)
    drive = only when the target is nearly centred, and slower the closer it is.
"""
import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Image

GAIN = 1.2            # rad/s of turn per unit of image error
CENTRED = 0.12        # |error| below this counts as "pointing at it"
STOP_DISTANCE = 0.55  # metres from the camera to the cube
MAX_SPEED = 0.2       # m/s
MIN_RED_PIXELS = 12   # fewer red pixels than this = "I cannot see it"
SEARCH_TURN = 0.4     # rad/s while searching


def red_mask(rgb):
    """True where a pixel is clearly red (strong red, weak green and blue)."""
    r, g, b = rgb[..., 0].astype(np.int16), rgb[..., 1].astype(np.int16), rgb[..., 2].astype(np.int16)
    return (r > 120) & (r - g > 70) & (r - b > 70)


def image_to_array(msg):
    """sensor_msgs/Image (rgb8) -> HxWx3 uint8. No cv_bridge needed."""
    return np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)


def steering(mask, depth_at_target):
    """(linear, angular, error) from a mask of red pixels; error is None if unseen."""
    if mask.sum() < MIN_RED_PIXELS:
        return 0.0, SEARCH_TURN, None
    centroid = float(np.nonzero(mask)[1].mean())
    half = mask.shape[1] / 2.0
    error = (centroid - half) / half
    angular = -GAIN * error
    linear = 0.0
    if abs(error) < CENTRED and depth_at_target is not None:
        if depth_at_target > STOP_DISTANCE:
            linear = min(MAX_SPEED, 0.5 * (depth_at_target - STOP_DISTANCE) + 0.05)
    return linear, angular, error


class ColorFollower(Node):
    def __init__(self):
        super().__init__("color_follower")
        self.depth = None
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(Image, "camera/depth", self.on_depth, 10)
        self.create_subscription(Image, "camera/image_raw", self.on_image, 10)
        self.get_logger().info("waiting for /camera/image_raw ...")

    def on_depth(self, msg):
        self.depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)

    def on_image(self, msg):
        if msg.encoding not in ("rgb8",):
            self.get_logger().warn(f"expected rgb8, got {msg.encoding}", throttle_duration_sec=5.0)
            return
        mask = red_mask(image_to_array(msg))
        depth_at_target = None
        if self.depth is not None and mask.any():
            d = self.depth[mask[: self.depth.shape[0], : self.depth.shape[1]]]
            d = d[np.isfinite(d) & (d > 0.05)]
            if d.size:
                depth_at_target = float(np.median(d))
        linear, angular, error = steering(mask, depth_at_target)
        cmd = Twist()
        cmd.linear.x = float(linear)
        cmd.angular.z = float(angular)
        self.cmd_pub.publish(cmd)
        self.get_logger().info(
            "red cube not visible: searching" if error is None else
            f"error {error:+.2f}  depth {depth_at_target if depth_at_target is not None else float('nan'):.2f} m  "
            f"-> v {linear:.2f} m/s, w {angular:+.2f} rad/s", throttle_duration_sec=1.0)


def main(args=None):
    rclpy.init(args=args)
    node = ColorFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.cmd_pub.publish(Twist())
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
