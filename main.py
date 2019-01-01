


import time

import sys
import flags
import signal
import multiprocessing
import multiprocessing.managers
import threading
import logSetup
import xascraper.status_monitor

from apscheduler.schedulers.background import BackgroundScheduler

import xascraper.modules.da.daScrape as das
import xascraper.modules.fa.faScrape as fas
import xascraper.modules.hf.hfScrape as hfs
import xascraper.modules.px.pxScrape as pxs
import xascraper.modules.wy.wyScrape as wys
import xascraper.modules.ib.ibScrape as ibs
import xascraper.modules.sf.sfScrape as sfs
import xascraper.modules.artstation.asScrape as ass
import xascraper.modules.tumblr.tumblrScrape as tus
import xascraper.modules.patreon.patreonScrape as pts
import xascraper.modules.yiff_party.yiff_scrape as yps

from settings import settings
import cherrypy

class Nopper():
	pluginName = "Nop Job"
	def __init__(self):
		pass
	def go(self, *args, **kwargs):
		print("Empty job looping!")
		pass

JOBS = [
	(das.GetDA,      settings["da" ]["runInterval"],  "da"),
	(fas.GetFA,      settings["fa" ]["runInterval"],  "fa"),
	(hfs.GetHF,      settings["hf" ]["runInterval"],  "hf"),
	(wys.GetWy,      settings["wy" ]["runInterval"],  "wy"),
	(ibs.GetIb,      settings["ib" ]["runInterval"],  "ib"),
	(pxs.GetPX,      settings["px" ]["runInterval"],  "px"),
	(sfs.GetSf,      settings["sf" ]["runInterval"],  "sf"),
	(pts.GetPatreon, settings["pat"]["runInterval"], "pat"),
	(Nopper,                                     30,  "yp"),
]


JOBS_DISABLED = [
	(ass.GetAs,      settings["as" ]["runInterval"],  "as"),
	(yps.GetYp,      settings["yp" ]["runInterval"],  "yp"),
	(tus.GetTumblr,  settings["tum"]["runInterval"], "tum"),
	(tus.GetTumblr,  settings["ng" ]["runInterval"],  "ng"),
]

# Yeah, this has to be after the job init. Sigh.
import xascraper


def runScraper(scraper_class, managed_namespace):
	print("Scheduler executing class: ", scraper_class)
	instance = scraper_class()
	instance.go(ctrlNamespace=managed_namespace)

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
		sched.add_job(runScraper, trigger='interval', seconds=interval, start_date='2014-1-4 0:00:00', name=name, args=(scraperClass, managedNamespace,))
	# sched.add_interval_job(printWat, seconds=10, start_date='2014-1-1 01:00')



def go(managedNamespace):
	print("Go()")


	resetter = xascraper.status_monitor.StatusResetter()
	resetter.resetRunState()

	# statusMgr = manage.statusDbManager.StatusResource()
	managedNamespace.run = True
	managedNamespace.serverRun = True


	server_process = multiprocessing.Process(target=serverProcess, args=(managedNamespace,))
	if "debug" in sys.argv:
		print("Not starting scheduler due to debug mode!")
		sched = None
	else:
		sched = BackgroundScheduler({
				'apscheduler.jobstores.default': {
					'type': 'memory'
				},
				'apscheduler.executors.default': {
					'class': 'apscheduler.executors.pool:ProcessPoolExecutor',
					'max_workers': '5'
				},
				'apscheduler.job_defaults.coalesce': 'true',
				'apscheduler.job_defaults.max_instances': '1',
			})

		scheduleJobs(sched, managedNamespace)
		sched.start()
		print("Scheduler is running!")

	print("Launching server process")
	server_process.start()
	loopCtr = 0

	print("Entering idle loop.")
	while managedNamespace.run:
		time.sleep(0.1)
		# if loopCtr % 100 == 0:
		# 	for job in sched.get_jobs():
		# 		print("Job: ", job.name, job.next_run_time.timestamp())
		# 		# statusMgr.updateNextRunTime(job.name, job.next_run_time.timestamp())
		loopCtr += 1

	if sched:
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
