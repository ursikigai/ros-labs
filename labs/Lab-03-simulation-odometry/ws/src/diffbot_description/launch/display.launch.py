import os

import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("diffbot_description")
    urdf = os.path.join(share, "urdf", "diffbot.urdf.xacro")
    robot_description = xacro.process_file(urdf).toxml()

    return LaunchDescription(
        [
            DeclareLaunchArgument("gui", default_value="true", description="Joint slider GUI"),
            DeclareLaunchArgument("rviz", default_value="true", description="Start RViz2"),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description}],
            ),
            Node(
                package="joint_state_publisher_gui",
                executable="joint_state_publisher_gui",
                condition=IfCondition(LaunchConfiguration("gui")),
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", os.path.join(share, "rviz", "diffbot.rviz")],
                condition=IfCondition(LaunchConfiguration("rviz")),
            ),
        ]
    )
