import math
import os

import numpy as np
import xacro

from diffbot_sim import kinematics as kin
from diffbot_sim.world import GridWorld, default_world

URDF = os.path.join(
    os.path.dirname(__file__), "..", "..", "diffbot_description", "urdf", "diffbot.urdf.xacro"
)


def test_wheel_speeds_roundtrip():
    for v, w in [(0.3, 0.0), (0.0, 1.0), (0.2, -0.7), (-0.1, 0.4)]:
        l, r = kin.wheel_speeds(v, w, 0.05, 0.30)
        v2, w2 = kin.body_twist(l, r, 0.05, 0.30)
        assert math.isclose(v, v2, abs_tol=1e-12) and math.isclose(w, w2, abs_tol=1e-12)


def test_step_pose_straight_and_arc():
    assert kin.step_pose(0, 0, 0, 1.0, 0.0, 2.0) == (2.0, 0.0, 0.0)
    # Quarter circle of radius 1: v=1, w=1 for pi/2 seconds ends at (1, 1) facing +y.
    x, y, th = kin.step_pose(0, 0, 0, 1.0, 1.0, math.pi / 2)
    assert math.isclose(x, 1.0, abs_tol=1e-9) and math.isclose(y, 1.0, abs_tol=1e-9)
    assert math.isclose(th, math.pi / 2)


def test_slipped_wheels_make_real_motion_differ_from_encoders():
    cmd_l, cmd_r = kin.wheel_speeds(0.2, 0.0, 0.05, 0.30)  # drive straight
    # no error: real motion equals the command
    assert kin.slipped_wheel_speeds(cmd_l, cmd_r) == (cmd_l, cmd_r)
    # a right wheel that is 3 % "faster" makes a straight command curve to the left
    l, r = kin.slipped_wheel_speeds(cmd_l, cmd_r, right_bias=0.03)
    assert l == cmd_l and r > cmd_r
    v, w = kin.body_twist(l, r, 0.05, 0.30)
    assert w > 0.0 and v > 0.2
    # jitter acts independently per wheel
    l2, r2 = kin.slipped_wheel_speeds(cmd_l, cmd_r, jitter_left=-0.1, jitter_right=0.1)
    assert l2 < cmd_l and r2 > cmd_r


def test_quaternion_roundtrip():
    for yaw in (-2.5, -0.3, 0.0, 1.2, 3.0):
        _, _, z, w = kin.yaw_to_quaternion(yaw)
        assert math.isclose(kin.quaternion_to_yaw(z, w), yaw, abs_tol=1e-9)


def test_raycast_hits_wall_at_known_distance():
    grid = np.zeros((100, 100), dtype=bool)
    grid[:, 80:] = True  # wall starting at x = 4.0 m (res 0.05)
    world = GridWorld(grid, 0.05)
    r = world.raycast(1.0, 2.5, [0.0], 10.0)[0]
    assert abs(r - 3.0) < 0.06
    assert np.isinf(world.raycast(1.0, 2.5, [math.pi], 1.0)[0])  # nothing within 1 m


def test_default_world_layout():
    world = default_world()
    assert world.is_occupied(3.1, 2.0)  # wall 1
    assert not world.is_occupied(3.1, 6.0)  # gap above wall 1
    assert world.is_occupied(-1.0, 1.0)  # outside counts as wall
    assert not world.circle_collides(1.0, 1.0, 0.17)  # start pose is free
    assert world.circle_collides(3.1, 2.0, 0.17)
    assert not world.is_occupied(8.5, 6.5)  # goal pose is free


def test_geometry_matches_urdf():
    """The simulator defaults must agree with the robot model."""
    root = xacro.process_file(URDF).documentElement
    radius = None
    for cyl in root.getElementsByTagName("cylinder"):
        node = cyl
        while node.tagName != "link":  # cylinder -> geometry -> visual -> link
            node = node.parentNode
        if node.getAttribute("name") == "left_wheel_link":
            radius = float(cyl.getAttribute("radius"))
            break
    ys = [
        float(j.getElementsByTagName("origin")[0].getAttribute("xyz").split()[1])
        for j in root.getElementsByTagName("joint")
        if j.getAttribute("name") in ("left_wheel_joint", "right_wheel_joint")
    ]
    assert math.isclose(radius, 0.05)
    assert math.isclose(abs(ys[0] - ys[1]), 0.30)
