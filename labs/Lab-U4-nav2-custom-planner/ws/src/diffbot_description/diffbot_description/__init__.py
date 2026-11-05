import os

import xacro
from ament_index_python.packages import get_package_share_directory


def load_geometry():
    """Return (wheel_radius, wheel_separation) parsed from the URDF so that the
    simulator and odometry share one source of truth with the robot model."""
    urdf = os.path.join(
        get_package_share_directory("diffbot_description"), "urdf", "diffbot.urdf.xacro"
    )
    root = xacro.process_file(urdf).documentElement
    radius = None
    for cyl in root.getElementsByTagName("cylinder"):
        node = cyl
        while node.tagName != "link":  # cylinder -> geometry -> visual -> link
            node = node.parentNode
        if node.getAttribute("name") == "left_wheel_link":
            radius = float(cyl.getAttribute("radius"))
            break
    ys = {}
    for joint in root.getElementsByTagName("joint"):
        name = joint.getAttribute("name")
        if name in ("left_wheel_joint", "right_wheel_joint"):
            origin = joint.getElementsByTagName("origin")[0]
            ys[name] = float(origin.getAttribute("xyz").split()[1])
    separation = abs(ys["left_wheel_joint"] - ys["right_wheel_joint"])
    return radius, separation
