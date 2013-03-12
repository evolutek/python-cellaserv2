#!/usr/bin/env python3

try:
    import local_settings
    HOST, PORT = local_settings.HOST, local_settings.PORT
except:
    import os
    import configparser

    config = configparser.ConfigParser()
    config.read(['/etc/conf.d/cellaserv'])

    HOST = os.environ.get("CS_HOST",
            config.get("client", "host", fallback="evolutek.org"))
    PORT = int(os.environ.get("CS_PORT",
        config.get("client", "port", fallback="4200")))
