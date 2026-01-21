"""Setup configuration for climate-search-api."""

from setuptools import setup, find_packages

setup(
    name="climate-search-api",
    version="1.0.0",
    packages=find_packages(include=["src", "src.*"]),
    package_dir={"": "."},
    python_requires=">=3.10",
    install_requires=[
        # Dependencies are in requirements.txt
    ],
)
