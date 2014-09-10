


import time

import flags
import signal
import multiprocessing
import threading
import logSetup


import wsgi_server

import cherrypy




def runServer():


	cherrypy.tree.graft(wsgi_server.app, "/")

	# Unsubscribe the default server
	cherrypy.server.unsubscribe()

	# Instantiate a new server object
	server = cherrypy._cpserver.Server()

	# Configure the server object
	server.socket_host = "0.0.0.0"
	server.socket_port = 6543
	server.thread_pool = 30

	# For SSL Support
	# server.ssl_module            = 'pyopenssl'
	# server.ssl_certificate       = 'ssl/certificate.crt'
	# server.ssl_private_key       = 'ssl/private.key'
	# server.ssl_certificate_chain = 'ssl/bundle.crt'

	# Subscribe this server
	server.subscribe()

	# Example for a 2nd server (same steps as above):
	# Remember to use a different port

	# server2             = cherrypy._cpserver.Server()

	# server2.socket_host = "0.0.0.0"
	# server2.socket_port = 8081
	# server2.thread_pool = 30
	# server2.subscribe()

	# Start the server engine (Option 1 *and* 2)

	cherrypy.engine.start()
	cherrypy.engine.block()



def serverProcess(runState):

	webThread = threading.Thread(target=runServer)
	webThread.start()

	while runState.value:
		time.sleep(0.1)

	print("Stopping server.")
	cherrypy.engine.exit()
	print("Server stopped")

def go():

	flags.serverRun = multiprocessing.Value("b", True)
	server_process = multiprocessing.Process(target=serverProcess, args=(flags.serverRun,))

	server_process.start()

	while flags.run:
		time.sleep(0.1)

	server_process.join()



def signal_handler(dummy_signal, dummy_frame):
	if flags.run:
		flags.run = False
		flags.serverRun.value=False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

if __name__ == "__main__":
	signal.signal(signal.SIGINT, signal_handler)
	logSetup.initLogging()
	go()
