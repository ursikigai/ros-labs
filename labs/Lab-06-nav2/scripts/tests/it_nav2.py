"""Real Nav2 driving DiffBot in the course simulator (nav2.launch.py), in two modes.

  NAV2_PLANNER=navfn  (default)  Nav2's own NavFn planner + Regulated Pure Pursuit: cross the room around both walls.
  NAV2_PLANNER=custom            the ORIGINAL robotics_essentials_ros2 C++ plugin (custom_nav2_planner/CustomPlanner),
                                 which asks a `create_plan` service for the path. This test process provides that
                                 service (a straight-line planner: my own solution to the repo's exercise 5).

Run:  pixi run test-nav2            (navfn)
      pixi run test-essentials      (custom; needs  pixi run build-essentials  first)
"""
import math
import os
import time

import harness  # noqa: F401
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry, Path
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Int32
from std_srvs.srv import Trigger

MODE = os.environ.get("NAV2_PLANNER", "navfn")
START = (1.0, 1.0)
GOALS = {"navfn": (8.5, 6.5), "custom": (2.2, 3.0)}


class Probe(Node):
    def __init__(self):
        super().__init__("nav2_probe")
        self.truth = None
        self.collisions = 0
        self.plan = None
        self.plan_count = 0
        self.travelled = 0.0
        self._last = None
        self.create_subscription(Odometry, "ground_truth", self.on_truth, 10)
        self.create_subscription(Int32, "collision_count", lambda m: setattr(self, "collisions", m.data), 10)
        self.create_subscription(Path, "plan", self.on_plan, 10)
        self.client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.active_client = self.create_client(Trigger, "lifecycle_manager_navigation/is_active")
        self.requests = []  # (start_xy, goal_xy) of every create_plan request (custom mode)
        if MODE == "custom":
            from create_plan_msgs.srv import CreatePlan  # from the Essentials overlay
            self.create_service(CreatePlan, "create_plan", self.on_create_plan)

    def on_truth(self, msg):
        self.truth = msg
        p = msg.pose.pose.position
        if self._last is not None:
            self.travelled += math.hypot(p.x - self._last[0], p.y - self._last[1])
        self._last = (p.x, p.y)

    def on_plan(self, msg):
        if msg.poses:
            self.plan = msg
            self.plan_count += 1

    def on_create_plan(self, request, response):
        """Straight-line planner: the repo's exercise 5, solved. Points every 0.1 m between start and goal."""
        s, g = request.start.pose.position, request.goal.pose.position
        self.requests.append(((s.x, s.y), (g.x, g.y)))
        path = Path()
        path.header.frame_id = request.goal.header.frame_id
        path.header.stamp = self.get_clock().now().to_msg()
        steps = max(1, int(math.hypot(g.x - s.x, g.y - s.y) / 0.1))
        for i in range(steps + 1):
            t = i / steps
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = s.x + t * (g.x - s.x)
            pose.pose.position.y = s.y + t * (g.y - s.y)
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        response.path = path
        return response


def line_deviation(poses, a, b):
    """Largest distance of any pose from the segment a-b."""
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay)
    worst = 0.0
    for p in poses:
        px, py = p.pose.position.x, p.pose.position.y
        t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / (length * length)))
        worst = max(worst, math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay))))
    return worst


def main():
    goal_xy = GOALS[MODE]
    c = harness.Checker(f"Real Nav2 on the course simulator (planner: {MODE})")
    launch_args = ["diffbot_bringup", "nav2.launch.py", f"planner:={MODE}"]
    with harness.launched(*launch_args, log_name=f"nav2_{MODE}"):
        rclpy.init()
        probe = Probe()

        def nav2_active():
            if not probe.active_client.service_is_ready():
                return False
            fut = probe.active_client.call_async(Trigger.Request())
            harness.wait_until(probe, fut.done, timeout=10.0)
            return fut.done() and fut.result().success

        up = harness.wait_until(probe, lambda: probe.truth is not None and nav2_active(), timeout=300.0)
        c.check(up, "all Nav2 lifecycle nodes (controller, planner, behaviors, bt_navigator) became ACTIVE")
        c.check(probe.client.wait_for_server(timeout_sec=60.0), "Nav2's navigate_to_pose action server is available")
        harness.wait_until(probe, lambda: False, timeout=5.0)  # costmaps need a moment to fill

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x, goal.pose.pose.position.y = goal_xy
        goal.pose.pose.orientation.w = 1.0
        fut = probe.client.send_goal_async(goal)
        harness.wait_until(probe, fut.done, timeout=30.0)
        handle = fut.result()
        c.check(handle is not None and handle.accepted, f"goal {goal_xy} accepted by Nav2")
        result = None
        if handle and handle.accepted:
            res_fut = handle.get_result_async()
            harness.wait_until(probe, res_fut.done, timeout=300.0)
            result = res_fut.result() if res_fut.done() else None
        ok = result is not None and result.status == GoalStatus.STATUS_SUCCEEDED
        c.check(ok, f"Nav2 reports the navigation SUCCEEDED (status {getattr(result, 'status', None)})")

        p = probe.truth.pose.pose.position
        dist = math.hypot(p.x - goal_xy[0], p.y - goal_xy[1])
        straight = math.hypot(goal_xy[0] - START[0], goal_xy[1] - START[1])
        print(f"final position ({p.x:.2f}, {p.y:.2f}), {dist:.2f} m from goal; travelled {probe.travelled:.1f} m (straight line {straight:.1f} m)")
        c.check(dist < 0.35, f"robot ended within 0.35 m of the goal ({dist:.2f} m)")
        c.check(probe.collisions == 0, f"no collisions ({probe.collisions})")
        c.check(probe.plan is not None, f"Nav2 published a global plan on /plan ({probe.plan_count} times)")

        if MODE == "navfn":
            c.check(probe.travelled > straight * 1.15, "robot detoured around the walls (not a straight line)")
        else:
            c.check(len(probe.requests) >= 1, f"Nav2's C++ plugin called our create_plan service ({len(probe.requests)} requests)")
            c.check(probe.plan is not None and line_deviation(probe.plan.poses, START, goal_xy) < 0.03,
                    "the published plan is exactly our straight line (the plugin passed our path through)")
            c.check(probe.travelled < straight * 1.3, f"robot drove roughly straight ({probe.travelled:.1f} m for {straight:.1f} m)")
        probe.destroy_node()
        rclpy.shutdown()
    c.finish()


if __name__ == "__main__":
    main()
