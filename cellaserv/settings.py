#!/usr/bin/env python3

import logging

try:
    import local_settings
    HOST, PORT = local_settings.HOST, local_settings.PORT
    DEBUG = "0"
except:
    import os
    import configparser

    config = configparser.ConfigParser()
    config.read(['/etc/conf.d/cellaserv'])

    HOST = os.environ.get("CS_HOST",
            config.get("client", "host", fallback="evolutek.org"))
    PORT = int(os.environ.get("CS_PORT",
        config.get("client", "port", fallback="4200")))

    DEBUG = int(os.environ.get("CS_DEBUG",
        config.get("client", "debug", fallback="0")))

logging.basicConfig()

def get_socket():
    import socket
    return socket.create_connection((HOST, PORT))
