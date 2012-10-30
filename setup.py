from setuptools import setup

setup(
    name='python-cellaserv',
    version='0.4',
    url='evolutek.org',
    description='Python client for cellaserv',
    author='Evolutek',
    author_email='mail@halfr.net',

    packages = ['cellaserv'],
    entry_points = {
        'console_scripts': [
            'cellasend = cellaserv.cellasend:main'
            ]
        },

    test_suite = 'tests.unit_tests',
)
