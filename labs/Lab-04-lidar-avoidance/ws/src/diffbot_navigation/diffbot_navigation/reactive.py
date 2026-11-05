"""Reactive obstacle avoidance from a LaserScan (pure Python, no ROS)."""
import math

STOP_DIST = 0.45
SLOW_DIST = 0.90
MAX_V = 0.25
MAX_W = 1.0
FRONT_HALF_ANGLE = math.radians(30)
SIDE_MAX_ANGLE = math.radians(90)
NO_RETURN = 10.0  # value used for inf/nan ranges


def _sector_min(angles, ranges, lo, hi):
    vals = [r for a, r in zip(angles, ranges) if lo <= a <= hi]
    return min(vals) if vals else NO_RETURN


def _sector_mean(angles, ranges, lo, hi):
    vals = [r for a, r in zip(angles, ranges) if lo <= a <= hi]
    return sum(vals) / len(vals) if vals else NO_RETURN


def clean_ranges(ranges, range_max=NO_RETURN):
    return [r if (r is not None and math.isfinite(r)) else range_max for r in ranges]


def compute_command(ranges, angle_min, angle_increment, turn_dir=0):
    """Return (v, w, turn_dir).

    `turn_dir` is +1/-1 while the robot is turning away from an obstacle and 0 otherwise.
    Remembering it avoids dithering left/right when both sides look equally open.
    """
    ranges = clean_ranges(ranges)
    angles = [angle_min + i * angle_increment for i in range(len(ranges))]

    front = _sector_min(angles, ranges, -FRONT_HALF_ANGLE, FRONT_HALF_ANGLE)
    left = _sector_mean(angles, ranges, FRONT_HALF_ANGLE, SIDE_MAX_ANGLE)
    right = _sector_mean(angles, ranges, -SIDE_MAX_ANGLE, -FRONT_HALF_ANGLE)

    if front < STOP_DIST:
        if turn_dir == 0:
            turn_dir = 1 if left >= right else -1  # turn towards the more open side
        return 0.0, MAX_W * turn_dir, turn_dir

    if turn_dir != 0 and front < SLOW_DIST:
        # Keep turning until there is comfortable room, then resume.
        return 0.05, 0.6 * MAX_W * turn_dir, turn_dir

    # Free ahead: slow down as we approach, nudge away from the nearer side.
    scale = min(1.0, (front - STOP_DIST) / (SLOW_DIST - STOP_DIST))
    v = max(0.05, MAX_V * scale)
    w = 0.0
    if front < SLOW_DIST:
        w = 0.5 * MAX_W * (1 if left >= right else -1)
    return v, w, 0
