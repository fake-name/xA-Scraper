


import time

import threading
import logging
import logSetup


# Shut up fucking annoying psycopg2 vomit every exec.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='psycopg2')

import cherrypy
from settings import settings
import xascraper


log = logging.getLogger("Main.Server")

def runServer():

	cherrypy.tree.graft(xascraper.app, "/")

	# Unsubscribe the default server
	cherrypy.server.unsubscribe()

	# Instantiate a new server object
	server = cherrypy._cpserver.Server()

	# Configure the server object
	server.socket_host = settings['server-conf']['listen-address']
	server.socket_port = settings['server-conf']['listen-port']
	server.thread_pool = settings['server-conf']['thread-pool-size']

	server.subscribe()

	cherrypy.engine.start()
	cherrypy.engine.block()


def run_web():

	webThread = threading.Thread(target=runServer)
	webThread.start()

	try:
		while True:
			time.sleep(0.1)
	except KeyboardInterrupt:
		pass

	log.info("Stopping server.")
	cherrypy.engine.exit()
	log.info("Server stopped")



if __name__ == "__main__":
	logSetup.initLogging()

	run_web()

