import math

from diffbot_odometry.odometry_math import update_pose, yaw_to_quaternion

SEP = 0.30


def test_straight_line():
    x, y, th = update_pose(0, 0, 0, 0.1, 0.1, SEP)
    assert math.isclose(x, 0.1) and math.isclose(y, 0.0, abs_tol=1e-12) and th == 0.0


def test_spin_in_place():
    # Wheels turn opposite ways by +-(pi/2 * SEP/2) -> pure 90 degree left turn.
    d = math.pi / 2 * SEP / 2
    x, y, th = update_pose(0, 0, 0, -d, d, SEP)
    assert math.isclose(th, math.pi / 2)
    assert math.isclose(x, 0.0, abs_tol=1e-12) and math.isclose(y, 0.0, abs_tol=1e-12)


def test_many_small_steps_match_exact_circle():
    # v = 0.2 m/s, w = 0.5 rad/s for 2*pi/0.5 s -> full circle returns to the start.
    v, w, dt = 0.2, 0.5, 0.001
    steps = int(2 * math.pi / w / dt)
    x = y = th = 0.0
    for _ in range(steps):
        dl = (v - w * SEP / 2) * dt
        dr = (v + w * SEP / 2) * dt
        x, y, th = update_pose(x, y, th, dl, dr, SEP)
    assert abs(x) < 5e-3 and abs(y) < 5e-3


def test_quaternion_is_unit():
    for yaw in (0.0, 1.0, -2.0, 3.0):
        qx, qy, qz, qw = yaw_to_quaternion(yaw)
        assert math.isclose(qx * qx + qy * qy + qz * qz + qw * qw, 1.0)
