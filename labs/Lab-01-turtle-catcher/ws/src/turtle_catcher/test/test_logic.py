import math
import random
from types import SimpleNamespace as T

from turtle_catcher import logic


def test_normalize_angle_wraps():
    assert math.isclose(logic.normalize_angle(3 * math.pi), math.pi, abs_tol=1e-9) or math.isclose(
        logic.normalize_angle(3 * math.pi), -math.pi, abs_tol=1e-9
    )
    assert math.isclose(logic.normalize_angle(0.5), 0.5)
    assert math.isclose(logic.normalize_angle(-2 * math.pi - 0.3), -0.3, abs_tol=1e-9)


def test_pick_target_closest_vs_first():
    turtles = [T(name="far", x=9, y=9), T(name="near", x=2, y=1)]
    assert logic.pick_target(1, 1, turtles, closest_first=True).name == "near"
    assert logic.pick_target(1, 1, turtles, closest_first=False).name == "far"
    assert logic.pick_target(1, 1, [], True) is None


def test_compute_command_straight_ahead():
    linear, angular = logic.compute_command(0, 0, 0.0, 2, 0)
    assert linear > 0 and math.isclose(angular, 0.0, abs_tol=1e-9)


def test_compute_command_turns_in_place_when_target_behind():
    linear, angular = logic.compute_command(0, 0, 0.0, -2, 0.1)
    assert linear == 0.0 and abs(angular) > 0


def test_random_spawn_pose_in_bounds():
    rng = random.Random(0)
    for _ in range(100):
        x, y, th = logic.random_spawn_pose(rng)
        assert 1.0 <= x <= 10.0 and 1.0 <= y <= 10.0 and 0.0 <= th <= 2 * math.pi
