import logging
from logging import getLogger, basicConfig

from werkzeug.contrib.fixers import ProxyFix

from config import Config
from main import app

getLogger().setLevel(logging.DEBUG)
logger = getLogger()
logger.info("Started with proxyfix")
ProxyFix(app, num_proxies=2)
basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    if Config.DEBUG:
        logger.info("Starting in debug!")
        app.run(debug=True, use_evalex=True, host="0.0.0.0", port=5000)
    else:
        logger.info("Starting in production.")
        app.run(debug=True, use_evalex=False, host="127.0.0.1")
