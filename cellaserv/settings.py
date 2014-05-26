#!/usr/bin/env python3

import configparser
import logging
import os
import socket

logging.basicConfig()

config = configparser.ConfigParser()
config.read(['/etc/conf.d/cellaserv'])

HOST = "evolutek.org"
try:
    HOST = config.get("client", "host")
except:
    pass
HOST = os.environ.get("CS_HOST", HOST)

PORT = 4200
try:
    PORT = int(config.get("client", "port"))
except:
    pass
PORT = int(os.environ.get("CS_PORT", PORT))

DEBUG = 0
try:
    DEBUG = int(config.get("client", "debug"))
except:
    pass
DEBUG = int(os.environ.get("CS_DEBUG", DEBUG))

ROBOT = None
try:
    ROBOT = config.get("client", "robot")
except:
    pass
ROBOT = os.environ.get("CS_ROBOT", ROBOT)


def get_socket():
    """Open a socket to cellaserv using user configuration."""
    return socket.create_connection((HOST, PORT))
