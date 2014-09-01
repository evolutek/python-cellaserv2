#!/usr/bin/env python3
import inspect
import configparser
import logging
import os
import socket

logging.basicConfig()

config = configparser.ConfigParser()
config.read(['/etc/conf.d/cellaserv'])


def make_setting(name, default, cfg_section, cfg_option, env, coerc=str):
    val = default
    try:
        val = config.get(cfg_section, cfg_option)
    except:
        pass
    val = coerc(os.environ.get(env, val))
    # Inject in the current global namespace
    globals()[name] = val

def make_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG >= 1 else logging.INFO)
    return logger

make_setting('HOST', 'evolutek.org', 'client', 'host', 'CS_HOST')
make_setting('PORT', 4200, 'client', 'port', 'CS_PORT', int)
make_setting('DEBUG', 0, 'client', 'debug', 'CS_DEBUG', int)


def get_socket():
    """Open a socket to cellaserv using user configuration."""
    return socket.create_connection((HOST, PORT))

logger = make_logger(__name__)
logger.debug("DEBUG: %s", DEBUG)
logger.debug("HOST: %s", HOST)
logger.debug("PORT: %s", PORT)
