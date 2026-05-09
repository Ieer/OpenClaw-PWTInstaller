from glob import glob
from pathlib import Path

from setuptools import find_packages, setup

package_name = "openclaw_voice_stack"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test", "tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "PyYAML"],
    zip_safe=True,
    maintainer="OpenClaw maintainers",
    maintainer_email="maintainers@example.com",
    description="ROS2 audio stack for OpenClaw Mission Control voice integration.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "wake_node = openclaw_voice_stack.wake_node:main",
            "asr_node = openclaw_voice_stack.asr_node:main",
            "tts_node = openclaw_voice_stack.tts_node:main",
            "mc_tts_feedback_node = openclaw_voice_stack.mc_tts_feedback_node:main",
            "manual_turn_node = openclaw_voice_stack.manual_turn_node:main",
        ],
    },
)
