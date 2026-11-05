"""Class 3 bringup: simulator + robot model + wheel odometry (+ optional RViz).

Frames:  map --(static, = start pose)--> odom --(odometry_node)--> base_footprint --(RSP)--> ...
"""
import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    desc_share = get_package_share_directory("diffbot_description")
    robot_description = xacro.process_file(
        os.path.join(desc_share, "urdf", "diffbot.urdf.xacro")
    ).toxml()

    args = [
        DeclareLaunchArgument("rviz", default_value="false"),
        DeclareLaunchArgument("initial_x", default_value="1.0"),
        DeclareLaunchArgument("initial_y", default_value="1.0"),
        DeclareLaunchArgument("initial_yaw", default_value="0.0"),
        DeclareLaunchArgument("wheel_noise", default_value="0.0"),
        DeclareLaunchArgument("wheel_bias", default_value="0.0"),
    ]
    x, y, yaw = (LaunchConfiguration(n) for n in ("initial_x", "initial_y", "initial_yaw"))

    return LaunchDescription(
        args
        + [
            Node(
                package="diffbot_sim",
                executable="sim_node",
                parameters=[
                    {
                        "initial_x": x,
                        "initial_y": y,
                        "initial_yaw": yaw,
                        "wheel_noise": LaunchConfiguration("wheel_noise"),
                        "wheel_bias": LaunchConfiguration("wheel_bias"),
                    }
                ],
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description}],
            ),
            Node(package="diffbot_odometry", executable="odometry_node"),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                arguments=[
                    "--x", x, "--y", y, "--yaw", yaw,
                    "--frame-id", "map", "--child-frame-id", "odom",
                ],
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", os.path.join(desc_share, "rviz", "diffbot.rviz")],
                condition=IfCondition(LaunchConfiguration("rviz")),
            ),
        ]
    )
