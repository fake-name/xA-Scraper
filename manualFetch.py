


import time

import flags
import signal
import multiprocessing
import threading
import logSetup


import wsgi_server

import sys
import main

def print_help():
	print("Run with `python manualFetch.py [plugin name]`")
	print("where [plugin name] is one of the following:")
	for plugin_cls, interval, key in main.JOBS:
		print("	Name: {} -> {}".format("'{}'".format(key).rjust(5), plugin_cls.pluginName))


def go():
	if len(sys.argv) == 1:
		print_help()
		return
	plg_name = sys.argv[1]
	print("Attempting to find plugin '{}'".format(plg_name))

	plug_lut = {item[2] : item[0] for item in main.JOBS}

	if not plg_name in plug_lut:
		print("ERROR! Plugin: {} not in available plugins: {}".format(plg_name, list(plug_lut.keys())))
		print_help()
		print("Note: Do not use quotes!")
		return
	plg = plug_lut[plg_name]
	print(plg)


	manager = multiprocessing.managers.SyncManager()
	manager.start()
	namespace = manager.Namespace()
	namespace.run=True


	plg.runScraper(namespace)


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
