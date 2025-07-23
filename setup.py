from setuptools import setup, find_packages

setup(
    name="specvalid",
    version="0.0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "specvalid=cli:main",
        ],
    },
)
