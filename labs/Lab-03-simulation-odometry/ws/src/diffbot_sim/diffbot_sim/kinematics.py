"""Differential-drive kinematics (pure Python, no ROS)."""
import math


def step_pose(x, y, theta, v, w, dt):
    """Integrate a unicycle model exactly over dt for constant (v, w)."""
    if abs(w) < 1e-9:
        return x + v * math.cos(theta) * dt, y + v * math.sin(theta) * dt, theta
    new_theta = theta + w * dt
    x += v / w * (math.sin(new_theta) - math.sin(theta))
    y += -v / w * (math.cos(new_theta) - math.cos(theta))
    return x, y, new_theta


def wheel_speeds(v, w, wheel_radius, wheel_separation):
    """Body twist -> (left, right) wheel angular velocities [rad/s]."""
    left = (v - w * wheel_separation / 2.0) / wheel_radius
    right = (v + w * wheel_separation / 2.0) / wheel_radius
    return left, right


def slipped_wheel_speeds(left, right, right_bias=0.0, jitter_left=0.0, jitter_right=0.0):
    """Speeds the wheels REALLY move the robot with, given the commanded (ideal) speeds.

    Slip (random jitter) and a wheel that is slightly bigger or smaller than assumed (right_bias, a constant
    fraction) change the real motion. The encoders still report the *commanded* rotation, and that gap between
    "what the encoders say" and "what really happened" is exactly why wheel odometry drifts.
    """
    return left * (1.0 + jitter_left), right * (1.0 + right_bias + jitter_right)


def body_twist(left_vel, right_vel, wheel_radius, wheel_separation):
    """(left, right) wheel angular velocities -> (v, w). Inverse of wheel_speeds."""
    v_left = left_vel * wheel_radius
    v_right = right_vel * wheel_radius
    return (v_right + v_left) / 2.0, (v_right - v_left) / wheel_separation


def yaw_to_quaternion(yaw):
    """Return (x, y, z, w) for a rotation about Z."""
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def quaternion_to_yaw(z, w):
    return 2.0 * math.atan2(z, w)
