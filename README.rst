python-cellaserv2
=================

Python3 library for cellaserv2.

Install
-------

Requirements:

google-protobuf with python3 support: https://github.com/malthe/google-protobuf

Installing ``google-protobuf`` for python3::

    $ git clone https://github.com/malthe/google-protobuf.git
    $ cd google-protobuf
    $ ./autogen.sh
    $ ./configure
    $ make
    $ cd python
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

- Rémi Audebert, Evolutek 2012-2015
- Benoît Reitz, Evolutek 2013-2015
- Adrien Schildknecht, Evolutek 2013-2015
- Vincent Gatine, Evolutek 2014-2015
