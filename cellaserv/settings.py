#!/usr/bin/env python3

import configparser
import logging
import os
import socket

logging.basicConfig()

config = configparser.ConfigParser()
config.read(['/etc/conf.d/cellaserv'])

HOST = os.environ.get("CS_HOST",
        config.get("client", "host", fallback="evolutek.org"))
PORT = int(os.environ.get("CS_PORT",
    config.get("client", "port", fallback="4200")))

DEBUG = int(os.environ.get("CS_DEBUG",
    config.get("client", "debug", fallback="0")))

def get_socket():
    return socket.create_connection((HOST, PORT))
