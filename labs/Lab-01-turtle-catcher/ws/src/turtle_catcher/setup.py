from glob import glob

from setuptools import find_packages, setup

package_name = "turtle_catcher"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Course Maintainer",
    maintainer_email="ranjeetsingh-air@dsu.edu.in",
    description="Class 1 project: catch turtles in turtlesim.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "turtle_spawner = turtle_catcher.turtle_spawner:main",
            "turtle_controller = turtle_catcher.turtle_controller:main",
        ],
    },
)
