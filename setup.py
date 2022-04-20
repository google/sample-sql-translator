#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name='sample-sql-translator',
    url='https://github.com/google/sample-sql-translator',
    description='This package is a general-purpose SQL parser, translator, analyzer, and formatter.',
    install_requires=[],
    packages=find_packages(exclude=['examples']),
    include_package_data=True,
)
