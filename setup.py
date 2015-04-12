#!/usr/bin/env python

from distutils.core import setup



setup(
    name='fakeed',
    version='0.1',
    description='Fake torrent tracker upload statistics',
    url='https://github.com/maxisoft/fakeed',
    author='maxisoft',
    author_email='maxisoft@youpy.tk',
    install_requires=['tornado', 'pyyaml'],
    packages=['fakeed'],
)
