"""Class 5 end-to-end test: autonomous navigation (A* planner + NavigateToPose action).

  1. Sends a goal across the room; robot must reach it, using the S-shaped detour,
     with zero collisions.
  2. Sends a goal inside a wall; the action must be aborted with ERR_NO_PLAN (1).
Run:  pixi run test-class5
"""
import math
import time

import harness  # noqa: F401
import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry, Path
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Int32

GOAL = (8.5, 6.5)
WALL_GOAL = (3.1, 2.0)


class Probe(Node):
    def __init__(self):
        super().__init__("class5_probe")
        self.truth = None
        self.collisions = 0
        self.plan = None
        self.travelled = 0.0
        self._last = None
        self.trace = []
        self.create_subscription(Odometry, "ground_truth", self.on_truth, 10)
        self.create_subscription(Int32, "collision_count", lambda m: setattr(self, "collisions", m.data), 10)
        self.create_subscription(Path, "plan", lambda m: setattr(self, "plan", m), 10)
        self.client = ActionClient(self, NavigateToPose, "navigate_to_pose")

    def on_truth(self, msg):
        self.truth = msg
        p = msg.pose.pose.position
        now = time.monotonic()
        if now - getattr(self, "_trace_t", 0.0) > 1.5:  # coarse trajectory for diagnosis
            self._trace_t = now
            self.trace.append((round(p.x, 2), round(p.y, 2), round(2 * math.atan2(msg.pose.pose.orientation.z, msg.pose.pose.orientation.w), 2)))
        if self._last is not None:
            self.travelled += math.hypot(p.x - self._last[0], p.y - self._last[1])
        self._last = (p.x, p.y)

    def send_goal(self, xy):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x, goal.pose.pose.position.y = xy
        goal.pose.pose.orientation.w = 1.0
        future = self.client.send_goal_async(goal)
        harness.wait_until(self, future.done, timeout=15.0)
        return future.result()

    def wait_result(self, goal_handle, timeout):
        future = goal_handle.get_result_async()
        harness.wait_until(self, future.done, timeout=timeout)
        return future.result() if future.done() else None


def main():
    c = harness.Checker("Class 5 - autonomous navigation")
    with harness.launched("diffbot_bringup", "navigation.launch.py", log_name="class5"):
        rclpy.init()
        probe = Probe()
        c.check(
            harness.wait_until(
                probe,
                lambda: probe.truth is not None and probe.client.server_is_ready(),
                timeout=90.0,
            ),
            "simulator and navigator action server are up",
        )
        # Give the planner time to receive the latched map and TF to fill.
        harness.wait_until(probe, lambda: False, timeout=4.0)

        # ---- 1. reachable goal --------------------------------------------------------
        handle = probe.send_goal(GOAL)
        c.check(handle is not None and handle.accepted, "goal across the room accepted")
        result = probe.wait_result(handle, timeout=240.0) if handle and handle.accepted else None
        ok = result is not None and result.status == GoalStatus.STATUS_SUCCEEDED
        c.check(ok, f"navigation succeeded (status={getattr(result, 'status', None)}, "
                    f"msg={getattr(getattr(result, 'result', None), 'error_msg', '')!r})")
        p = probe.truth.pose.pose.position
        dist = math.hypot(p.x - GOAL[0], p.y - GOAL[1])
        straight = math.hypot(GOAL[0] - 1.0, GOAL[1] - 1.0)
        print(f"final position ({p.x:.2f}, {p.y:.2f}), {dist:.2f} m from goal; "
              f"travelled {probe.travelled:.1f} m (straight line {straight:.1f} m)")
        c.check(dist < 0.25, f"robot ended within 0.25 m of the goal ({dist:.2f} m)")
        c.check(probe.plan is not None and len(probe.plan.poses) > 20, "global plan was published on /plan")
        c.check(probe.travelled > straight * 1.15, "robot took a detour around the walls (not a straight line)")
        c.check(probe.collisions == 0, f"no collisions ({probe.collisions})")
        print("trajectory (x, y, yaw):", probe.trace)
        if probe.plan:
            pts = [(round(q.pose.position.x, 1), round(q.pose.position.y, 1)) for q in probe.plan.poses]
            print("plan (every 10th):", pts[::10] + [pts[-1]])

        # ---- 2. unreachable goal ------------------------------------------------------
        handle = probe.send_goal(WALL_GOAL)
        c.check(handle is not None and handle.accepted, "goal inside a wall is accepted by the server")
        result = probe.wait_result(handle, timeout=30.0) if handle and handle.accepted else None
        c.check(
            result is not None and result.status == GoalStatus.STATUS_ABORTED and result.result.error_code == 1,
            "goal inside a wall is aborted with ERR_NO_PLAN (1)",
        )
        probe.destroy_node()
        rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
