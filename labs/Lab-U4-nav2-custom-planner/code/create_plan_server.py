"""Lab U4: a straight-line planner served as a ROS 2 service.

Nav2's C++ plugin (custom_nav2_planner/CustomPlanner, from the Essentials repository) does not plan by itself:
whenever Nav2 needs a path it calls the service /create_plan (create_plan_msgs/srv/CreatePlan) and passes our
answer through unchanged. This node is that service. Replace the body of on_create_plan() with A*, Dijkstra, ...
to plug your own planner into Nav2.

Run it (see lab U4):  pixi run cmd /c scripts\\in_upstream.bat essentials python lab-manuals\\code\\create_plan_server.py
"""
import math

import rclpy
from create_plan_msgs.srv import CreatePlan
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node

STEP = 0.1  # metres between two points of the path


class StraightLinePlanner(Node):
    def __init__(self):
        super().__init__("straight_line_planner")
        self.create_service(CreatePlan, "create_plan", self.on_create_plan)
        self.get_logger().info("create_plan service ready")

    def on_create_plan(self, request, response):
        s, g = request.start.pose.position, request.goal.pose.position
        path = Path()
        path.header.frame_id = request.goal.header.frame_id
        path.header.stamp = self.get_clock().now().to_msg()
        steps = max(1, int(math.hypot(g.x - s.x, g.y - s.y) / STEP))
        for i in range(steps + 1):
            t = i / steps
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = s.x + t * (g.x - s.x)
            pose.pose.position.y = s.y + t * (g.y - s.y)
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        self.get_logger().info(f"plan ({s.x:.2f}, {s.y:.2f}) -> ({g.x:.2f}, {g.y:.2f}): {len(path.poses)} points")
        response.path = path
        return response


def main():
    rclpy.init()
    node = StraightLinePlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
