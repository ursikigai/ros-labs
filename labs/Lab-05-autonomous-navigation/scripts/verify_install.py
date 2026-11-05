"""Smoke test for the course environment.

Run with:  pixi run verify

Checks that rclpy can create a node, publish, and receive its own message
through the DDS middleware, with a hard timeout so it never hangs.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

TIMEOUT_S = 15.0


class Loopback(Node):
    def __init__(self):
        super().__init__("verify_install")
        self.received = None
        self.pub = self.create_publisher(String, "verify_topic", 10)
        self.create_subscription(String, "verify_topic", self.on_msg, 10)
        self.create_timer(0.2, self.tick)

    def tick(self):
        self.pub.publish(String(data="hello from ros2-pbl-course"))

    def on_msg(self, msg):
        self.received = msg.data


def main():
    rclpy.init()
    node = Loopback()
    deadline = time.monotonic() + TIMEOUT_S
    while rclpy.ok() and node.received is None and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    ok = node.received is not None
    print(f"received: {node.received!r}")
    print("PASS: rclpy pub/sub works" if ok else "FAIL: no message received")
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
