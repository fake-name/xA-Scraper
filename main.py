


import time

import flags
import signal
import multiprocessing
import multiprocessing.managers
import threading
import logSetup

from apscheduler.schedulers.background import BackgroundScheduler

import plugins.scrapers.da.daScrape as das
import plugins.scrapers.fa.faScrape as fas
import plugins.scrapers.hf.hfScrape as hfs
import plugins.scrapers.px.pxScrape as pxs
import plugins.scrapers.wy.wyScrape as wys
import plugins.scrapers.ib.ibScrape as ibs
import plugins.scrapers.sf.sfScrape as sfs
import plugins.scrapers.artstation.asScrape as ass
import plugins.scrapers.tumblr.tumblrScrape as tus

from settings import settings
import cherrypy

import manage.statusDbManager


JOBS = [
	(das.GetDA,     settings["da"]["runInterval"],   "da"),
	(fas.GetFA,     settings["fa"]["runInterval"],   "fa"),
	(hfs.GetHF,     settings["hf"]["runInterval"],   "hf"),
	(wys.GetWy,     settings["wy"]["runInterval"],   "wy"),
	(ibs.GetIb,     settings["ib"]["runInterval"],   "ib"),
	(pxs.GetPX,     settings["px"]["runInterval"],   "px"),
	(sfs.GetSf,     settings["sf"]["runInterval"],   "sf"),
	(ass.GetAs,     settings["as"]["runInterval"],   "as"),
	(tus.GetTumblr, settings["tum"]["runInterval"], "tum"),
]


import rewrite



def runServer():

	cherrypy.tree.graft(rewrite.app, "/")

	# Unsubscribe the default server
	cherrypy.server.unsubscribe()

	# Instantiate a new server object
	server = cherrypy._cpserver.Server()

	# Configure the server object
	server.socket_host = "0.0.0.0"
	server.socket_port = 6543
	server.thread_pool = 30

	server.subscribe()

	cherrypy.engine.start()
	cherrypy.engine.block()



def serverProcess(managedNamespace):

	webThread = threading.Thread(target=runServer)
	webThread.start()

	while managedNamespace.serverRun:
		time.sleep(0.1)

	print("Stopping server.")
	cherrypy.engine.exit()
	print("Server stopped")


def scheduleJobs(sched, managedNamespace):


	for scraperClass, interval, name in JOBS:

		print(scraperClass, interval)
		sched.add_job(scraperClass.runScraper, trigger='interval', seconds=interval, start_date='2014-1-4 0:00:00', name=name, args=(managedNamespace,))
	# sched.add_interval_job(printWat, seconds=10, start_date='2014-1-1 01:00')



def go(managedNamespace):
	statusMgr = manage.statusDbManager.StatusResource()
	managedNamespace.run = True
	managedNamespace.serverRun = True


	server_process = multiprocessing.Process(target=serverProcess, args=(managedNamespace,))

	sched = BackgroundScheduler()

	# scheduleJobs(sched, managedNamespace)
	# server_process.start()
	# sched.start()

	loopCtr = 0
	while managedNamespace.run:
		time.sleep(0.1)

		if loopCtr % 100 == 0:
			for job in sched.get_jobs():
				statusMgr.updateNextRunTime(job.name, job.next_run_time.timestamp())
		loopCtr += 1

	sched.shutdown()
	server_process.join()

def mgr_init():
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	print('initialized manager')

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		flags.namespace.serverRun = False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

if __name__ == "__main__":

	manager = multiprocessing.managers.SyncManager()
	manager.start(mgr_init)
	flags.namespace = manager.Namespace()

	signal.signal(signal.SIGINT, signal_handler)
	logSetup.initLogging()
	go(flags.namespace)

	manager.shutdown()
