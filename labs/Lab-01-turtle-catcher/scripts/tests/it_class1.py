"""Class 1 end-to-end test: Turtle Catcher (turtlesim + spawner + controller + custom interfaces).

Verifies, against the real launch file:
  * the custom CatchTurtle service answers (and rejects an unknown turtle),
  * turtles are spawned at roughly the configured rate,
  * the controller actually catches turtles (names that appeared on /alive_turtles and vanished),
  * the alive list stays bounded and turtle1 really moved.
Run:  pixi run test-class1
"""
import math
import time

import harness  # noqa: F401
import rclpy
from rclpy.node import Node
from turtle_catcher_interfaces.msg import TurtleArray
from turtle_catcher_interfaces.srv import CatchTurtle
from turtlesim.msg import Pose

RUN_SECONDS = 60.0


class Probe(Node):
    def __init__(self):
        super().__init__("class1_probe")
        self.seen = set()
        self.alive = set()
        self.max_alive = 0
        self.pose = None
        self.travelled = 0.0
        self.create_subscription(TurtleArray, "alive_turtles", self.on_alive, 10)
        self.create_subscription(Pose, "turtle1/pose", self.on_pose, 10)
        self.catch_client = self.create_client(CatchTurtle, "catch_turtle")

    def on_alive(self, msg):
        self.alive = {t.name for t in msg.turtles}
        self.seen |= self.alive
        self.max_alive = max(self.max_alive, len(self.alive))

    def on_pose(self, msg):
        if self.pose is not None:
            self.travelled += math.hypot(msg.x - self.pose.x, msg.y - self.pose.y)
        self.pose = msg


def main():
    c = harness.Checker("Class 1 - Turtle Catcher")
    with harness.launched("turtle_catcher", "turtle_catcher.launch.py", log_name="class1"):
        rclpy.init()
        probe = Probe()
        c.check(
            harness.wait_until(
                probe,
                lambda: probe.pose is not None and probe.catch_client.service_is_ready() and probe.seen,
                timeout=90.0,
            ),
            "turtlesim, spawner and controller are up and a turtle has spawned",
        )

        # Custom service contract: unknown names must be rejected, not crash the spawner.
        future = probe.catch_client.call_async(CatchTurtle.Request(name="no_such_turtle"))
        harness.wait_until(probe, future.done, timeout=10.0)
        c.check(
            future.done() and future.result().success is False,
            "CatchTurtle rejects an unknown turtle (success=False)",
        )

        start = time.monotonic()
        while time.monotonic() - start < RUN_SECONDS:
            rclpy.spin_once(probe, timeout_sec=0.1)

        caught = probe.seen - probe.alive
        print(f"spawned: {len(probe.seen)}, caught: {len(caught)}, alive now: {len(probe.alive)}, "
              f"max alive: {probe.max_alive}, turtle1 travelled {probe.travelled:.1f}")
        c.check(len(probe.seen) >= 30, f"~1 turtle/s spawned over {RUN_SECONDS:.0f} s ({len(probe.seen)} >= 30)")
        c.check(len(caught) >= 5, f"controller caught turtles ({len(caught)} >= 5)")
        c.check(probe.max_alive < 15, f"alive list stays bounded (max {probe.max_alive} < 15)")
        c.check(probe.travelled > 10.0, f"turtle1 moved ({probe.travelled:.1f} units)")
        probe.destroy_node()
        rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
