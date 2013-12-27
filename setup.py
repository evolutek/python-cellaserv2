from setuptools import setup

setup(
    name='python-cellaserv',
    version='3',
    url='evolutek.org',
    description='Python client for cellaserv',
    author='Remi Audebert - Evolutek 2013-2014',
    author_email='contact@halfr.net',
    install_requires=['pygments'],

    packages=['cellaserv'],

    test_suite='tests.unit_tests',
)
