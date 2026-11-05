"""Class 5: NavigateToPose action server (same interface as Nav2, so RViz's goal tool works).

Pipeline per goal:  pose from TF -> GetPlan service -> pure-pursuit loop -> cmd_vel.
"""
import math
import threading
import time

import rclpy
from geometry_msgs.msg import PoseStamped, Twist, Vector3
from nav2_msgs.action import NavigateToPose
from nav_msgs.srv import GetPlan
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

from diffbot_navigation import pure_pursuit

# Result error codes (0 = success), mirrored in the course docs.
ERR_NONE, ERR_NO_PLAN, ERR_NO_POSE, ERR_BLOCKED, ERR_TIMEOUT = 0, 1, 2, 3, 4


class Navigator(Node):
    def __init__(self):
        super().__init__("navigator")
        self.declare_parameter("goal_tolerance", 0.15)
        self.declare_parameter("timeout_s", 240.0)
        self.declare_parameter("blocked_distance", 0.20)
        self.tolerance = self.get_parameter("goal_tolerance").value
        self.timeout = self.get_parameter("timeout_s").value
        self.blocked_distance = self.get_parameter("blocked_distance").value

        self.cb_group = ReentrantCallbackGroup()
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=True)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.plan_client = self.create_client(GetPlan, "plan_path", callback_group=self.cb_group)
        self.front_min = float("inf")
        self.create_subscription(
            LaserScan, "scan", self.on_scan, 10, callback_group=self.cb_group
        )
        self.server = ActionServer(
            self,
            NavigateToPose,
            "navigate_to_pose",
            execute_callback=self.execute,
            goal_callback=lambda goal: GoalResponse.ACCEPT,
            cancel_callback=lambda goal: CancelResponse.ACCEPT,
            callback_group=self.cb_group,
        )
        self.get_logger().info("Navigator ready (action: navigate_to_pose)")

    # --- helpers ---------------------------------------------------------
    def on_scan(self, scan):
        lo = -math.radians(20)
        vals = [
            r
            for i, r in enumerate(scan.ranges)
            if lo <= scan.angle_min + i * scan.angle_increment <= -lo and math.isfinite(r)
        ]
        self.front_min = min(vals) if vals else float("inf")

    def robot_pose(self):
        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", Time())
        except Exception:  # TF not available yet
            return None
        q = t.transform.rotation
        return t.transform.translation.x, t.transform.translation.y, 2.0 * math.atan2(q.z, q.w)

    def stop(self):
        self.cmd_pub.publish(Twist())

    def request_plan(self, start_xy, goal_pose):
        request = GetPlan.Request()
        request.start.header.frame_id = "map"
        request.start.pose.position.x, request.start.pose.position.y = start_xy
        request.start.pose.orientation.w = 1.0
        request.goal = goal_pose
        request.tolerance = 0.0
        future = self.plan_client.call_async(request)
        end = time.monotonic() + 10.0
        while not future.done() and time.monotonic() < end:
            time.sleep(0.02)  # other executor threads complete the future
        return future.result().plan if future.done() else None

    def finish(self, goal_handle, code, text, success):
        self.stop()
        result = NavigateToPose.Result(error_code=code, error_msg=text)
        if success:
            goal_handle.succeed()
        elif goal_handle.is_cancel_requested:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        self.get_logger().info(f"Goal finished: {text or 'success'}")
        return result

    # --- action ----------------------------------------------------------
    def execute(self, goal_handle):
        goal = goal_handle.request.pose
        gx, gy = goal.pose.position.x, goal.pose.position.y
        self.get_logger().info(f"Navigating to ({gx:.2f}, {gy:.2f})")

        pose = None
        deadline = time.monotonic() + 5.0
        while pose is None and time.monotonic() < deadline:
            pose = self.robot_pose()
            time.sleep(0.05)
        if pose is None:
            return self.finish(goal_handle, ERR_NO_POSE, "map->base_footprint TF unavailable", False)

        plan = self.request_plan((pose[0], pose[1]), goal)
        if plan is None or not plan.poses:
            return self.finish(goal_handle, ERR_NO_PLAN, "planner returned no path", False)
        path = [(p.pose.position.x, p.pose.position.y) for p in plan.poses]
        goal_xy = (gx, gy)

        start_time = time.monotonic()
        index = 0
        blocked_since = None
        progress_anchor, progress_time = (pose[0], pose[1]), time.monotonic()
        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                return self.finish(goal_handle, ERR_NONE, "cancelled", False)
            if time.monotonic() - start_time > self.timeout:
                return self.finish(goal_handle, ERR_TIMEOUT, "navigation timed out", False)

            pose = self.robot_pose()
            if pose is None:
                time.sleep(0.05)
                continue
            x, y, yaw = pose
            dist = math.hypot(gx - x, gy - y)
            if dist < self.tolerance:
                return self.finish(goal_handle, ERR_NONE, "", True)

            # Safety: something right in front of us for more than 2 s -> give up.
            if self.front_min < self.blocked_distance:
                blocked_since = blocked_since or time.monotonic()
                if time.monotonic() - blocked_since > 2.0:
                    return self.finish(goal_handle, ERR_BLOCKED, "path blocked by obstacle", False)
            else:
                blocked_since = None

            # Stuck detector: must move at least 5 cm every 8 s (rotation in place is brief).
            if math.hypot(x - progress_anchor[0], y - progress_anchor[1]) > 0.05:
                progress_anchor, progress_time = (x, y), time.monotonic()
            elif time.monotonic() - progress_time > 8.0:
                return self.finish(goal_handle, ERR_BLOCKED, "no progress (stuck)", False)

            index = pure_pursuit.closest_index(path, x, y, index)
            target = pure_pursuit.lookahead_point(path, index, x, y)
            v, w = pure_pursuit.compute_command(x, y, yaw, target, goal_xy)
            self.cmd_pub.publish(Twist(linear=Vector3(x=float(v)), angular=Vector3(z=float(w))))

            feedback = NavigateToPose.Feedback()
            feedback.current_pose = PoseStamped()
            feedback.current_pose.header.frame_id = "map"
            feedback.current_pose.pose.position.x = x
            feedback.current_pose.pose.position.y = y
            feedback.distance_remaining = float(dist)
            goal_handle.publish_feedback(feedback)
            time.sleep(0.05)
        return self.finish(goal_handle, ERR_NO_POSE, "shutdown", False)


def main(args=None):
    rclpy.init(args=args)
    node = Navigator()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
