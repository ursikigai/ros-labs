import math

import numpy as np

from diffbot_navigation import planning, pure_pursuit, reactive
from diffbot_sim.world import default_world

# ---------------------------------------------------------------- reactive


def scan(front=10.0, left=10.0, right=10.0, n=360):
    """Build a 360-ray scan with chosen minimum distances in the 3 sectors."""
    inc = 2 * math.pi / n
    ranges = []
    for i in range(n):
        a = -math.pi + i * inc
        if abs(a) <= math.radians(30):
            ranges.append(front)
        elif math.radians(30) < a <= math.radians(90):
            ranges.append(left)
        elif -math.radians(90) <= a < -math.radians(30):
            ranges.append(right)
        else:
            ranges.append(10.0)
    return ranges, -math.pi, inc


def test_reactive_clear_path_drives_straight():
    v, w, d = reactive.compute_command(*scan())
    assert v == reactive.MAX_V and w == 0.0 and d == 0


def test_reactive_blocked_front_stops_and_turns_to_open_side():
    v, w, d = reactive.compute_command(*scan(front=0.3, left=3.0, right=0.5))
    assert v == 0.0 and w > 0 and d == 1
    v, w, d = reactive.compute_command(*scan(front=0.3, left=0.5, right=3.0))
    assert v == 0.0 and w < 0 and d == -1


def test_reactive_keeps_turn_direction_until_clear():
    ranges = scan(front=0.7)  # between stop and slow distance
    v, w, d = reactive.compute_command(*ranges, turn_dir=-1)
    assert w < 0 and d == -1
    v, w, d = reactive.compute_command(*scan(front=3.0), turn_dir=-1)
    assert d == 0 and v == reactive.MAX_V


def test_reactive_handles_inf_and_nan():
    ranges, amin, inc = scan()
    ranges[0] = float("inf")
    ranges[1] = float("nan")
    v, _, _ = reactive.compute_command(ranges, amin, inc)
    assert v > 0


# ---------------------------------------------------------------- planning


def test_inflate_grows_obstacle_by_radius():
    g = np.zeros((21, 21), dtype=bool)
    g[10, 10] = True
    out = planning.inflate(g, 3)
    assert out[10, 13] and out[13, 10] and not out[10, 14] and not out[13, 13]
    assert out.sum() > g.sum()


def test_astar_goes_around_wall_and_reports_no_path_when_enclosed():
    g = np.zeros((20, 20), dtype=bool)
    g[:15, 10] = True  # wall with a gap at the bottom
    path = planning.astar(g, (2, 2), (2, 17))
    assert path and path[0] == (2, 2) and path[-1] == (2, 17)
    assert all(not g[c] for c in path)
    assert any(r >= 15 for r, _ in path)  # had to pass through the gap
    g[:, 10] = True  # seal it
    assert planning.astar(g, (2, 2), (2, 17)) is None


def test_astar_rejects_blocked_endpoints():
    g = np.zeros((5, 5), dtype=bool)
    g[0, 0] = True
    assert planning.astar(g, (0, 0), (4, 4)) is None


def test_shortcut_reduces_waypoints_without_crossing_walls():
    g = np.zeros((30, 30), dtype=bool)
    g[:20, 15] = True
    path = planning.astar(g, (2, 2), (2, 27))
    short = planning.shortcut(path, g)
    assert len(short) < len(path)
    for a, b in zip(short, short[1:]):
        assert planning.line_of_sight(g, a, b)


def test_resample_spacing():
    pts = planning.resample([(0, 0), (1, 0)], 0.1)
    assert len(pts) == 11
    assert all(math.hypot(b[0] - a[0], b[1] - a[1]) <= 0.1 + 1e-9 for a, b in zip(pts, pts[1:]))


def test_plan_across_default_world():
    world = default_world()
    blocked = planning.inflate(world.grid, int(math.ceil(0.30 / world.resolution)))
    start = world.world_to_cell(1.0, 1.0)
    goal = world.world_to_cell(8.5, 6.5)
    assert not blocked[start] and not blocked[goal]
    path = planning.astar(blocked, start, goal)
    assert path is not None
    xy = [world.cell_to_world(r, c) for r, c in planning.shortcut(path, blocked)]
    length = planning.path_length(xy)
    straight = math.hypot(7.5, 5.5)
    assert straight < length < 2.5 * straight  # must detour, but not absurdly
    for x, y in planning.resample(xy, 0.05):
        # Robot radius 0.17 plus >= 0.10 m left over for path-tracking error.
        assert not world.circle_collides(x, y, 0.27), f"path too close to an obstacle at ({x:.2f},{y:.2f})"


def test_goal_inside_wall_is_blocked():
    world = default_world()
    blocked = planning.inflate(world.grid, 4)
    assert blocked[world.world_to_cell(3.1, 2.0)]


# ------------------------------------------------------------ pure pursuit


def test_pure_pursuit_straight_and_behind():
    v, w = pure_pursuit.compute_command(0, 0, 0.0, (1, 0), (3, 0))
    assert v > 0 and abs(w) < 1e-9
    v, w = pure_pursuit.compute_command(0, 0, 0.0, (-1, 0.1), (-3, 0))
    assert v == 0.0 and abs(w) > 0


def test_pure_pursuit_slows_near_goal():
    far, _ = pure_pursuit.compute_command(0, 0, 0.0, (1, 0), (5, 0))
    near, _ = pure_pursuit.compute_command(0, 0, 0.0, (0.2, 0), (0.2, 0))
    assert near < far


def test_lookahead_and_closest_index():
    path = [(i * 0.1, 0.0) for i in range(30)]
    assert pure_pursuit.closest_index(path, 0.52, 0.0) == 5
    tx, _ = pure_pursuit.lookahead_point(path, 5, 0.5, 0.0, 0.4)
    assert math.isclose(tx, 0.9, abs_tol=1e-9)
    assert pure_pursuit.lookahead_point(path, 28, 2.8, 0.0, 0.4) == path[-1]
