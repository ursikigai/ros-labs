"""Spawns turtles at a fixed rate, publishes the alive list, and serves `catch_turtle`."""
import rclpy
from rclpy.node import Node
from turtle_catcher_interfaces.msg import Turtle, TurtleArray
from turtle_catcher_interfaces.srv import CatchTurtle
from turtlesim.srv import Kill, Spawn

from turtle_catcher.logic import random_spawn_pose


class TurtleSpawner(Node):
    def __init__(self):
        super().__init__("turtle_spawner")
        self.declare_parameter("spawn_frequency", 1.0)
        self.declare_parameter("turtle_name_prefix", "turtle")

        self.prefix = self.get_parameter("turtle_name_prefix").value
        frequency = self.get_parameter("spawn_frequency").value

        self.counter = 0
        self.alive = []  # list[Turtle]

        self.spawn_client = self.create_client(Spawn, "spawn")
        self.kill_client = self.create_client(Kill, "kill")
        self.alive_pub = self.create_publisher(TurtleArray, "alive_turtles", 10)
        self.create_service(CatchTurtle, "catch_turtle", self.catch_callback)
        self.create_timer(1.0 / frequency, self.spawn_turtle)

    def spawn_turtle(self):
        if not self.spawn_client.service_is_ready():
            self.get_logger().info("Waiting for /spawn ...", throttle_duration_sec=2.0)
            return
        self.counter += 1
        x, y, theta = random_spawn_pose()
        request = Spawn.Request(x=x, y=y, theta=theta, name=f"{self.prefix}{self.counter}")
        self.spawn_client.call_async(request).add_done_callback(
            lambda future, req=request: self.on_spawned(future, req)
        )

    def on_spawned(self, future, request):
        response = future.result()
        if response is None or not response.name:
            return
        self.alive.append(Turtle(name=response.name, x=request.x, y=request.y, theta=request.theta))
        self.get_logger().info(f"Spawned {response.name} at ({request.x:.1f}, {request.y:.1f})")
        self.publish_alive()

    def publish_alive(self):
        self.alive_pub.publish(TurtleArray(turtles=self.alive))

    def catch_callback(self, request, response):
        known = [t for t in self.alive if t.name == request.name]
        if not known:
            response.success = False
            return response
        self.alive.remove(known[0])
        self.kill_client.call_async(Kill.Request(name=request.name))
        self.get_logger().info(f"Caught {request.name}")
        self.publish_alive()
        response.success = True
        return response


def main(args=None):
    rclpy.init(args=args)
    node = TurtleSpawner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
