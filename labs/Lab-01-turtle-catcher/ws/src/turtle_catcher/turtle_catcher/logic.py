"""Pure-Python logic for the Turtle Catcher (no ROS imports, so it is unit-testable)."""
import math
import random

CATCH_DISTANCE = 0.5  # metres (turtlesim units)
LINEAR_GAIN = 2.0
ANGULAR_GAIN = 6.0
MAX_LINEAR = 3.0


def normalize_angle(angle):
    """Wrap an angle to the interval [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def pick_target(pose_x, pose_y, turtles, closest_first=True):
    """Choose which turtle to chase.

    `turtles` is a list of objects with .name .x .y. Returns None when empty.
    """
    if not turtles:
        return None
    if not closest_first:
        return turtles[0]
    return min(turtles, key=lambda t: distance(pose_x, pose_y, t.x, t.y))


def compute_command(pose_x, pose_y, pose_theta, target_x, target_y):
    """Proportional controller. Returns (linear, angular) velocity."""
    dist = distance(pose_x, pose_y, target_x, target_y)
    heading_error = normalize_angle(
        math.atan2(target_y - pose_y, target_x - pose_x) - pose_theta
    )
    linear = min(LINEAR_GAIN * dist, MAX_LINEAR)
    # Turn in place first when the target is far off to the side/behind.
    if abs(heading_error) > math.pi / 3:
        linear = 0.0
    return linear, ANGULAR_GAIN * heading_error


def random_spawn_pose(rng=random):
    """Random pose inside the 11x11 turtlesim window (with a margin)."""
    return rng.uniform(1.0, 10.0), rng.uniform(1.0, 10.0), rng.uniform(0.0, 2 * math.pi)
