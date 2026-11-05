"""Class 5: global planner. Serves nav_msgs/GetPlan on `plan_path` using A* on /map."""
import math

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid, Path
from nav_msgs.srv import GetPlan
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from diffbot_navigation import planning


class PlannerServer(Node):
    def __init__(self):
        super().__init__("planner_server")
        # Robot radius is 0.17 m; the extra 0.13 m absorbs path-tracking error.
        self.declare_parameter("inflation_radius", 0.30)
        self.declare_parameter("path_spacing", 0.10)
        self.inflation_radius = self.get_parameter("inflation_radius").value
        self.spacing = self.get_parameter("path_spacing").value

        self.map_info = None
        self.blocked = None

        latched = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.create_subscription(OccupancyGrid, "map", self.on_map, latched)
        self.plan_pub = self.create_publisher(Path, "plan", 10)
        self.create_service(GetPlan, "plan_path", self.on_plan_request)

    def on_map(self, msg):
        grid = np.array(msg.data, dtype=np.int8).reshape(msg.info.height, msg.info.width)
        occupied = (grid > 50) | (grid < 0)  # occupied or unknown
        cells = int(math.ceil(self.inflation_radius / msg.info.resolution))
        self.blocked = planning.inflate(occupied, cells)
        self.map_info = msg.info
        self.get_logger().info(
            f"Map received {msg.info.width}x{msg.info.height} @ {msg.info.resolution} m; "
            f"inflated by {cells} cells"
        )

    # --- helpers ---------------------------------------------------------
    def to_cell(self, x, y):
        res = self.map_info.resolution
        return int(math.floor((y - self.map_info.origin.position.y) / res)), int(
            math.floor((x - self.map_info.origin.position.x) / res)
        )

    def to_world(self, cell):
        res = self.map_info.resolution
        return (
            self.map_info.origin.position.x + (cell[1] + 0.5) * res,
            self.map_info.origin.position.y + (cell[0] + 0.5) * res,
        )

    def in_bounds(self, cell):
        return 0 <= cell[0] < self.blocked.shape[0] and 0 <= cell[1] < self.blocked.shape[1]

    # --- service ---------------------------------------------------------
    def on_plan_request(self, request, response):
        response.plan = Path()
        response.plan.header.frame_id = "map"
        if self.blocked is None:
            self.get_logger().warn("Plan requested but no map yet")
            return response

        sx, sy = request.start.pose.position.x, request.start.pose.position.y
        gx, gy = request.goal.pose.position.x, request.goal.pose.position.y
        start, goal = self.to_cell(sx, sy), self.to_cell(gx, gy)
        if not self.in_bounds(start) or not self.in_bounds(goal):
            self.get_logger().warn("Start or goal is outside the map")
            return response
        if self.blocked[goal]:
            self.get_logger().warn(f"Goal ({gx:.2f}, {gy:.2f}) is inside an obstacle")
            return response
        if self.blocked[start]:  # robot may sit inside the safety margin: relax start only
            relaxed = planning.nearest_free(self.blocked, start, 8)
            if relaxed is None:
                self.get_logger().warn("Start is trapped inside an obstacle")
                return response
            start = relaxed

        cells = planning.astar(self.blocked, start, goal)
        if cells is None:
            self.get_logger().warn("No path found")
            return response

        cells = planning.shortcut(cells, self.blocked)
        points = [(sx, sy)] + [self.to_world(c) for c in cells[1:-1]] + [(gx, gy)]
        points = planning.resample(points, self.spacing)

        stamp = self.get_clock().now().to_msg()
        response.plan.header.stamp = stamp
        for x, y in points:
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.header.stamp = stamp
            pose.pose.position.x = float(x)
            pose.pose.position.y = float(y)
            pose.pose.orientation.w = 1.0
            response.plan.poses.append(pose)
        self.plan_pub.publish(response.plan)
        self.get_logger().info(
            f"Planned {len(points)} points, {planning.path_length(points):.2f} m"
        )
        return response


def main(args=None):
    rclpy.init(args=args)
    node = PlannerServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
