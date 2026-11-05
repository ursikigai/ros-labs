"""Real Nav2 on the course simulator: controller + planner + behaviors + BT navigator, started by a lifecycle manager.

    pixi run ros launch diffbot_bringup nav2.launch.py                  # Nav2's own NavFn planner
    pixi run ros launch diffbot_bringup nav2.launch.py planner:=custom  # the Essentials repo's C++ plugin (needs its overlay)

The simulator supplies /map, /scan, /odom and TF (map -> odom -> base_footprint -> base_link), so no AMCL or
map_server is needed. The action is the standard `navigate_to_pose`, so `pixi run goto X Y` and RViz work unchanged.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory("diffbot_bringup")
    params = os.path.join(share, "config", "nav2_diffbot.yaml")
    planner = LaunchConfiguration("planner")

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share, "launch", "sim.launch.py")),
        launch_arguments={"rviz": "false", "wheel_noise": "0.0"}.items(),
    )
    plugin = PythonExpression(
        ["'custom_nav2_planner/CustomPlanner' if '", planner, "' == 'custom' else 'nav2_navfn_planner::NavfnPlanner'"]
    )
    lifecycle_nodes = ["controller_server", "planner_server", "behavior_server", "bt_navigator"]

    return LaunchDescription(
        [
            DeclareLaunchArgument("planner", default_value="navfn", description="navfn (Nav2 stock) or custom (Essentials plugin)"),
            DeclareLaunchArgument("rviz", default_value="false"),
            GroupAction([sim], scoped=True),
            Node(package="nav2_controller", executable="controller_server", output="screen", parameters=[params]),
            Node(package="nav2_planner", executable="planner_server", output="screen",
                 parameters=[params, {"GridBased.plugin": plugin}]),
            Node(package="nav2_behaviors", executable="behavior_server", output="screen", parameters=[params]),
            Node(package="nav2_bt_navigator", executable="bt_navigator", output="screen", parameters=[params]),
            Node(
                package="nav2_lifecycle_manager", executable="lifecycle_manager", name="lifecycle_manager_navigation",
                output="screen",
                # bond_timeout 0 disables heartbeat bonds: node start-up on Windows is slow enough to trip the default 4 s.
                parameters=[{"autostart": True, "node_names": lifecycle_nodes, "bond_timeout": 0.0}],
            ),
            Node(
                package="rviz2", executable="rviz2", output="screen",
                arguments=["-d", os.path.join(share, "config", "navigation.rviz")],
                condition=IfCondition(LaunchConfiguration("rviz")),
            ),
        ]
    )
