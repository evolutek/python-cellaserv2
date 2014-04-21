#!/usr/bin/env python3

import configparser
import logging
import os
import socket

logging.basicConfig()

config = configparser.ConfigParser()
config.read(['/etc/conf.d/cellaserv'])

try:
    HOST = os.environ.get("CS_HOST", config.get("client", "host"))
except:
    HOST = "evolutek.org"

try:
    PORT = int(os.environ.get("CS_PORT",
        config.get("client", "port")))
except:
    PORT = 4200

try:
    DEBUG = int(os.environ.get("CS_DEBUG", config.get("client", "debug")))
except:
    DEBUG = 0

def get_socket():
    """Open a socket to cellaserv using user configuration."""
    return socket.create_connection((HOST, PORT))
