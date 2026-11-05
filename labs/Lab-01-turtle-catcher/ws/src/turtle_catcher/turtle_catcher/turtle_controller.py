"""Drives turtle1 towards the chosen target and calls `catch_turtle` when it gets close."""
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from turtle_catcher_interfaces.msg import TurtleArray
from turtle_catcher_interfaces.srv import CatchTurtle
from turtlesim.msg import Pose

from turtle_catcher import logic


class TurtleController(Node):
    def __init__(self):
        super().__init__("turtle_controller")
        self.declare_parameter("catch_closest_turtle_first", True)
        self.closest_first = self.get_parameter("catch_closest_turtle_first").value

        self.pose = None
        self.turtles = []
        self.target = None
        self.catching = False
        self.caught_count = 0

        self.cmd_pub = self.create_publisher(Twist, "turtle1/cmd_vel", 10)
        self.create_subscription(Pose, "turtle1/pose", self.on_pose, 10)
        self.create_subscription(TurtleArray, "alive_turtles", self.on_alive, 10)
        self.catch_client = self.create_client(CatchTurtle, "catch_turtle")
        self.create_timer(0.02, self.control_loop)

    def on_pose(self, msg):
        self.pose = msg

    def on_alive(self, msg):
        self.turtles = list(msg.turtles)

    def control_loop(self):
        if self.pose is None:
            return
        # Drop the target if it vanished (caught or killed elsewhere).
        if self.target and all(t.name != self.target.name for t in self.turtles):
            self.target = None
        if self.target is None:
            self.target = logic.pick_target(
                self.pose.x, self.pose.y, self.turtles, self.closest_first
            )
        if self.target is None:
            self.cmd_pub.publish(Twist())
            return

        dist = logic.distance(self.pose.x, self.pose.y, self.target.x, self.target.y)
        if dist < logic.CATCH_DISTANCE:
            self.cmd_pub.publish(Twist())
            self.request_catch()
            return

        linear, angular = logic.compute_command(
            self.pose.x, self.pose.y, self.pose.theta, self.target.x, self.target.y
        )
        self.cmd_pub.publish(Twist(linear=_vec(x=linear), angular=_vec(z=angular)))

    def request_catch(self):
        if self.catching or not self.catch_client.service_is_ready():
            return
        self.catching = True
        name = self.target.name
        self.catch_client.call_async(CatchTurtle.Request(name=name)).add_done_callback(
            lambda future: self.on_caught(future, name)
        )

    def on_caught(self, future, name):
        self.catching = False
        result = future.result()
        if result is not None and result.success:
            self.caught_count += 1
            self.get_logger().info(f"Caught {name} (total {self.caught_count})")
        self.target = None


def _vec(x=0.0, y=0.0, z=0.0):
    from geometry_msgs.msg import Vector3

    return Vector3(x=float(x), y=float(y), z=float(z))


def main(args=None):
    rclpy.init(args=args)
    node = TurtleController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
