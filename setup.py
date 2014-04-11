try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='python-cellaserv2',
    version='5',
    url='code.evolutek.org/python-cellaserv2',
    description='Python client for cellaserv2',
    author='Remi Audebert - Evolutek 2013-2014',
    author_email='contact@halfr.net',

    install_requires=open('requirements.txt').read().splitlines(),

    packages=['cellaserv', 'cellaserv.protobuf'],

    classifiers=[
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
)
