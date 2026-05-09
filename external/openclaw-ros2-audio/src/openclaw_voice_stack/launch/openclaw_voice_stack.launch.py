# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    package_share = get_package_share_directory("openclaw_voice_stack")
    default_config = os.path.join(package_share, "config", "default.yaml")
    config = LaunchConfiguration("config")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                default_value=default_config,
                description="YAML parameter file for OpenClaw voice stack nodes.",
            ),
            Node(
                package="openclaw_voice_stack",
                executable="wake_node",
                name="wake_node",
                output="screen",
                parameters=[config],
            ),
            Node(
                package="openclaw_voice_stack",
                executable="asr_node",
                name="asr_node",
                output="screen",
                parameters=[config],
            ),
            Node(
                package="openclaw_voice_stack",
                executable="tts_node",
                name="tts_node",
                output="screen",
                parameters=[config],
            ),
            Node(
                package="openclaw_voice_stack",
                executable="mc_tts_feedback_node",
                name="mc_tts_feedback_node",
                output="screen",
                parameters=[config],
            ),
        ]
    )
