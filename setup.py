#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name="burgher",
    version="1.0",
    description="Tree like static site generator.",
    author="Visgean",
    author_email="visgean@gmail.com",
    url="https://github.com/visgean/burgher",
    packages=[
        "burgher",
    ],
    package_dir={"burgher": "burgher"},
    license="MIT",
    keywords="static site generator",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
    install_requires=[],
)
