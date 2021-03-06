try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='python-cellaserv2',
    version='git',
    url='code.evolutek.org/python-cellaserv2',
    description='Python client for cellaserv2',
    author='Remi Audebert - Evolutek 2013-2014',
    author_email='contact@halfr.net',

    install_requires=open('requirements.txt').read().splitlines(),

    packages=['cellaserv', 'cellaserv.protobuf'],

    test_requires=['pytest', 'pytest-timeout'],

    classifiers=[
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
)
