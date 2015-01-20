#!/usr/bin/env python

from setuptools import setup

setup(
  name='lego-instructions',
  version='0.1',
  py_modules=['script'],
  install_requires=[
    'beautifulsoup4',
    'click',
    'clint',
    'iniparse',
    'requests'
  ],

  entry_points={
    'console_scripts': [
      'download-lego-instructions = script:cli',
    ],
  },
)
