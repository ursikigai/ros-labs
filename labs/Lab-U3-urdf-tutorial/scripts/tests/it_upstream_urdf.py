"""End-to-end test of the ORIGINAL ros/urdf_tutorial (branch `ros2`, cloned to upstream/urdf_tutorial-ros2).

Launches the clone's own display.launch.py for each of its eight example robots and checks that
  * the package in use is the CLONE (overlay), not the conda copy,
  * /robot_description matches the clone's source file (link + joint counts, after xacro expansion),
  * every link of the robot resolves in TF (robot_state_publisher + joint_state_publisher did their job).
Run:  pixi run test-urdf   (after  pixi run build-urdf)
"""
import os
import xml.etree.ElementTree as ET

import harness  # noqa: F401
import rclpy
import xacro
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = ["01-myfirst.urdf", "02-multipleshapes.urdf", "03-origins.urdf", "04-materials.urdf",
          "05-visual.urdf", "06-flexible.urdf", "07-physics.urdf", "08-macroed.urdf.xacro"]


class Probe(Node):
    def __init__(self):
        super().__init__("urdf_probe")
        self.description = None
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, "robot_description", lambda m: setattr(self, "description", m.data), latched)
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)


def structure(xml_text):
    root = ET.fromstring(xml_text)
    links = [e.get("name") for e in root.iter("link")]
    joints = [(e.get("name"), e.find("parent").get("link"), e.find("child").get("link")) for e in root.iter("joint")]
    return root.get("name"), links, joints


def main():
    c = harness.Checker("Original ros/urdf_tutorial (clone, branch ros2) - all 8 example robots")
    share = get_package_share_directory("urdf_tutorial")
    c.check("upstream_ws" in share, f"urdf_tutorial comes from the clone's overlay ({os.path.relpath(share, ROOT)})")
    rclpy.init()
    for model in MODELS:
        src = os.path.join(ROOT, "upstream", "urdf_tutorial-ros2", "urdf", model)
        expected_xml = xacro.process_file(src).toxml()
        _, exp_links, exp_joints = structure(expected_xml)
        with harness.launched("urdf_tutorial", "display.launch.py", f"model:=urdf/{model}", "gui:=false", log_name=f"urdf_{model}"):
            probe = Probe()
            got = harness.wait_until(probe, lambda: probe.description is not None, timeout=90.0)
            if not got:
                c.check(False, f"{model}: /robot_description published")
                probe.destroy_node()
                continue
            _, links, joints = structure(probe.description)
            c.check(sorted(links) == sorted(exp_links) and len(joints) == len(exp_joints),
                    f"{model}: published robot matches the source file ({len(links)} links, {len(joints)} joints)")
            root_link = next(l for l in links if l not in {j[2] for j in joints})
            resolved = harness.wait_until(
                probe, lambda: all(probe.buf.can_transform(root_link, l, Time()) for l in links), timeout=45.0)
            c.check(resolved, f"{model}: all {len(links)} links resolve in TF from '{root_link}'")
            probe.destroy_node()
    rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
