"""Class 4 bringup: the Class 3 stack + the reactive obstacle avoider."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("diffbot_bringup"), "launch", "sim.launch.py")
        ),
        launch_arguments={"rviz": LaunchConfiguration("rviz")}.items(),
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("rviz", default_value="false"),
            sim,
            Node(package="diffbot_navigation", executable="obstacle_avoider"),
        ]
    )
