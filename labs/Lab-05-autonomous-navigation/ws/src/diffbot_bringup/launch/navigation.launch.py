"""Class 5 bringup: the Class 3 stack + A* planner + NavigateToPose action server."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("diffbot_bringup")
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share, "launch", "sim.launch.py")),
        launch_arguments={"rviz": "false", "wheel_noise": LaunchConfiguration("wheel_noise")}.items(),
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("rviz", default_value="false"),
            DeclareLaunchArgument("wheel_noise", default_value="0.0"),
            # scoped=True: the include sets rviz:=false for the sim's own RViz; without a scope
            # that value leaked back here and silently disabled the navigation RViz below.
            GroupAction([sim], scoped=True),
            Node(package="diffbot_navigation", executable="planner_server"),
            Node(package="diffbot_navigation", executable="navigator"),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", os.path.join(share, "config", "navigation.rviz")],
                condition=IfCondition(LaunchConfiguration("rviz")),
            ),
        ]
    )
