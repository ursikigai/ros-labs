"""Class 4 end-to-end test: reactive obstacle avoidance with the simulated LiDAR.

Lets the avoider wander for 60 s and verifies the robot covers real distance without
hitting anything (the simulator counts every collision on /collision_count).
Run:  pixi run test-class4
"""
import math
import time

import harness  # noqa: F401
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Int32

DRIVE_SECONDS = 60.0


class Probe(Node):
    def __init__(self):
        super().__init__("class4_probe")
        self.truth = None
        self.collisions = 0
        self.create_subscription(Odometry, "ground_truth", lambda m: setattr(self, "truth", m), 10)
        self.create_subscription(Int32, "collision_count", lambda m: setattr(self, "collisions", m.data), 10)


def main():
    c = harness.Checker("Class 4 - LiDAR obstacle avoidance")
    with harness.launched("diffbot_bringup", "avoid.launch.py", log_name="class4"):
        rclpy.init()
        probe = Probe()
        c.check(
            harness.wait_until(probe, lambda: probe.truth is not None, timeout=90.0),
            "simulator is publishing ground truth",
        )
        # The avoider needs /scan to be flowing before the robot starts to move; give it a moment.
        harness.wait_until(probe, lambda: False, timeout=3.0)

        last = None
        travelled = 0.0
        visited = set()
        end = time.monotonic() + DRIVE_SECONDS
        while time.monotonic() < end:
            rclpy.spin_once(probe, timeout_sec=0.1)
            p = probe.truth.pose.pose.position
            if last is not None:
                travelled += math.hypot(p.x - last[0], p.y - last[1])
            last = (p.x, p.y)
            visited.add((int(p.x), int(p.y)))  # 1 m x 1 m cells

        print(f"distance travelled: {travelled:.1f} m, 1 m cells visited: {len(visited)}, collisions: {probe.collisions}")
        c.check(travelled > 8.0, f"robot covered real distance ({travelled:.1f} m > 8 m)")
        c.check(len(visited) >= 4, f"robot explored the room ({len(visited)} cells >= 4)")
        c.check(probe.collisions == 0, f"no collisions ({probe.collisions})")
        probe.destroy_node()
        rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
