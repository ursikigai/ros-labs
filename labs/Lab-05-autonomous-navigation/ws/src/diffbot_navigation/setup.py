from setuptools import find_packages, setup

package_name = "diffbot_navigation"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Course Maintainer",
    maintainer_email="ranjeetsingh-air@dsu.edu.in",
    description="DiffBot reactive + global navigation.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "obstacle_avoider = diffbot_navigation.obstacle_avoider:main",
            "planner_server = diffbot_navigation.planner_server:main",
            "navigator = diffbot_navigation.navigator:main",
        ]
    },
)
