#!/usr/bin/env python3

import configparser
import logging
import os
import socket

logging.basicConfig()

config = configparser.ConfigParser()
config.read(['/etc/conf.d/cellaserv'])

try:
    HOST = config.get("client", "host")
except:
    HOST = os.environ.get("CS_HOST", "evolutek.org")

try:
    PORT = int(config.get("client", "port"))
except:
    PORT = int(os.environ.get("CS_PORT", 4200))

try:
    DEBUG = int(config.get("client", "debug"))
except:
    DEBUG = int(os.environ.get("CS_DEBUG", 0))

try:
    ROBOT = config.get("client", "robot")
except:
    ROBOT = os.environ.get("CS_ROBOT", None)


def get_socket():
    """Open a socket to cellaserv using user configuration."""
    return socket.create_connection((HOST, PORT))
