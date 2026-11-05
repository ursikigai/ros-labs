from glob import glob

from setuptools import find_packages, setup

package_name = "diffbot_description"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/urdf", glob("urdf/*")),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/rviz", glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Course Maintainer",
    maintainer_email="ranjeetsingh-air@dsu.edu.in",
    description="DiffBot URDF/Xacro model.",
    license="Apache-2.0",
)
