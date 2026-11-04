from setuptools import setup, find_packages

setup(
    name="rig",
    version="0.1.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "requests>=2.25.0",
        "ansible>=4.0.0",
        "boto3>=1.26.0",
        "PyYAML>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "rig=cli.main:main",
        ],
    },
    author="mystack-cloud",
    description="Ephemeral remotes with full local parity for coding agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/mystack-cloud/rig",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)