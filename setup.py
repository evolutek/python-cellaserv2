from setuptools import setup

setup(
    name='python-cellaserv',
    version='1',
    url='evolutek.org',
    description='Python client for cellaserv',
    author='Evolutek',
    author_email='mail@halfr.net',

    packages = ['cellaserv'],
    entry_points = {
        'console_scripts': [
            'cellasend = cellaserv.cellasend:main',
            'cellaquery = cellaserv.cellaquery:main',
            'cellevent = cellaserv.cellevent:main',
            ]
        },

    test_suite = 'tests.unit_tests',
)
