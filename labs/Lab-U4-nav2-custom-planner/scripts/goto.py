"""Send DiffBot to (x, y) in the map frame and report progress.

Usage:  pixi run goto 8.5 6.5
Needs the Class 5 stack running:  pixi run demo-nav   (or ros2 launch diffbot_bringup navigation.launch.py)
Exit code 0 = reached, 1 = failed/aborted/cancelled, 2 = bad usage.
"""
import sys
import time

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

ERRORS = {0: "none", 1: "no plan", 2: "no pose (TF)", 3: "blocked / stuck", 4: "timeout"}


def main():
    if len(sys.argv) != 3:
        print("usage: pixi run goto <x> <y>      e.g. pixi run goto 8.5 6.5")
        return 2
    x, y = float(sys.argv[1]), float(sys.argv[2])

    rclpy.init()
    node = rclpy.create_node("goto")
    client = ActionClient(node, NavigateToPose, "navigate_to_pose")
    print("waiting for the navigator (up to 60 s) ...")
    if not client.wait_for_server(timeout_sec=60.0):
        print("FAILED: no /navigate_to_pose server. Is `pixi run demo-nav` running?")
        return 1

    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = "map"
    goal.pose.pose.position.x, goal.pose.pose.position.y = x, y
    goal.pose.pose.orientation.w = 1.0

    last_print = [0.0]

    def on_feedback(msg):
        if time.monotonic() - last_print[0] > 2.0:
            last_print[0] = time.monotonic()
            p = msg.feedback.current_pose.pose.position
            print(f"  at ({p.x:.2f}, {p.y:.2f}), {msg.feedback.distance_remaining:.2f} m to go")

    future = client.send_goal_async(goal, feedback_callback=on_feedback)
    rclpy.spin_until_future_complete(node, future)
    handle = future.result()
    if not handle.accepted:
        print("FAILED: goal rejected")
        return 1
    print(f"going to ({x}, {y}) ...")
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result()

    ok = result.status == GoalStatus.STATUS_SUCCEEDED
    code = result.result.error_code
    print(("REACHED the goal" if ok else f"FAILED: {ERRORS.get(code, code)} - {result.result.error_msg}"))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
