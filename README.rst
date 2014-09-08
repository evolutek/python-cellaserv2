python-cellaserv2
=================

Python3 library for cellaserv2.

Install
-------

Requirements:

- google-protobuf with python3 support: https://github.com/malthe/google-protobuf

It can be installed with the following commands::

    $ git clone https://github.com/malthe/google-protobuf.git
    $ cd google-protobuf/python
    $ python setup.py build
    $ python setup.py install

Installing ``python-cellaserv2``::

    $ git clone ssh://git@bitbucket.org/evolutek/python-cellaserv2.git
    $ cd python-cellaserv2
    $ git submodule init
    $ git submodule update cellaserv/protobuf
    $ python setup.py develop

Authors
-------

- Rémi Audebert, Evolutek 2013-2015