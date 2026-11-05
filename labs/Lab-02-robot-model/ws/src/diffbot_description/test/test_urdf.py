import os

import xacro

URDF = os.path.join(os.path.dirname(__file__), "..", "urdf", "diffbot.urdf.xacro")


def load():
    return xacro.process_file(URDF).documentElement


def test_xacro_expands_without_leftover_macros():
    xml = xacro.process_file(URDF).toxml()
    assert "xacro:" not in xml and "${" not in xml


def test_expected_links_and_joints():
    root = load()
    links = {l.getAttribute("name") for l in root.getElementsByTagName("link")}
    joints = {j.getAttribute("name"): j.getAttribute("type") for j in root.getElementsByTagName("joint")}
    assert {"base_footprint", "base_link", "left_wheel_link", "right_wheel_link", "lidar_link"} <= links
    assert joints["left_wheel_joint"] == "continuous"
    assert joints["right_wheel_joint"] == "continuous"
    assert joints["lidar_joint"] == "fixed"


def test_kinematic_tree_is_single_connected_tree():
    root = load()
    links = {l.getAttribute("name") for l in root.getElementsByTagName("link")}
    children = set()
    edges = 0
    for j in root.getElementsByTagName("joint"):
        children.add(j.getElementsByTagName("child")[0].getAttribute("link"))
        edges += 1
    roots = links - children
    assert roots == {"base_footprint"}
    assert edges == len(links) - 1  # a tree has n-1 edges


def test_wheel_geometry_values():
    root = load()
    ys = {}
    for j in root.getElementsByTagName("joint"):
        if j.getAttribute("name") in ("left_wheel_joint", "right_wheel_joint"):
            ys[j.getAttribute("name")] = float(
                j.getElementsByTagName("origin")[0].getAttribute("xyz").split()[1]
            )
    assert abs(ys["left_wheel_joint"] - 0.15) < 1e-9
    assert abs(ys["right_wheel_joint"] + 0.15) < 1e-9
