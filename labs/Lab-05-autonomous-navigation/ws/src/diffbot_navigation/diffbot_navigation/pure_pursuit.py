"""Pure-pursuit style path tracking (pure Python, no ROS)."""
import math

MAX_V = 0.25
MAX_W = 1.0
LOOKAHEAD = 0.35
HEADING_GAIN = 2.5


def normalize_angle(a):
    return math.atan2(math.sin(a), math.cos(a))


def closest_index(path, x, y, start_index=0, window=40):
    """Index of the path point nearest to (x, y), searching forward from start_index."""
    best, best_d = start_index, float("inf")
    for i in range(start_index, min(len(path), start_index + window)):
        d = math.hypot(path[i][0] - x, path[i][1] - y)
        if d < best_d:
            best, best_d = i, d
    return best


def lookahead_point(path, index, x, y, lookahead=LOOKAHEAD):
    """First path point at/after `index` that is at least `lookahead` from the robot."""
    for i in range(index, len(path)):
        if math.hypot(path[i][0] - x, path[i][1] - y) >= lookahead:
            return path[i]
    return path[-1]


def compute_command(x, y, yaw, target, goal, max_v=MAX_V, max_w=MAX_W):
    """Steer towards `target` (lookahead point); slow down when turning and near `goal`."""
    alpha = normalize_angle(math.atan2(target[1] - y, target[0] - x) - yaw)
    dist_goal = math.hypot(goal[0] - x, goal[1] - y)
    v = max_v * max(0.0, math.cos(alpha))
    v = min(v, 0.6 * dist_goal + 0.05)  # ease off on approach
    if abs(alpha) > math.radians(70):
        v = 0.0  # mostly facing away: rotate in place first
    w = max(-max_w, min(max_w, HEADING_GAIN * alpha))
    return v, w
