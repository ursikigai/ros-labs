"""Wheel-odometry math (pure Python, no ROS)."""
import math


def update_pose(x, y, theta, d_left, d_right, wheel_separation):
    """Advance a pose given how far each wheel travelled (metres) since the last update.

    Uses the midpoint heading for the translation, which is accurate for small steps.
    """
    ds = (d_left + d_right) / 2.0
    dtheta = (d_right - d_left) / wheel_separation
    x += ds * math.cos(theta + dtheta / 2.0)
    y += ds * math.sin(theta + dtheta / 2.0)
    return x, y, theta + dtheta


def yaw_to_quaternion(yaw):
    """Return (x, y, z, w) for a rotation about Z."""
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)
