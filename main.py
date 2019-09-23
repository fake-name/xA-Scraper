


import time

import sys
import flags
import datetime
import signal
import multiprocessing
import multiprocessing.managers
import threading
import logging
import logSetup


# Shut up fucking annoying psycopg2 vomit every exec.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='psycopg2')


import xascraper.status_monitor

import apscheduler.events
from apscheduler.schedulers.background import BackgroundScheduler

import xascraper.modules.da.daScrape as das
import xascraper.modules.fa.faScrape as fas
import xascraper.modules.hf.hfScrape as hfs
import xascraper.modules.px.pxScrape as pxs
import xascraper.modules.wy.wyScrape as wys
import xascraper.modules.ib.ibScrape as ibs
import xascraper.modules.sf.sfScrape as sfs
import xascraper.modules.ng.ngScrape as ngs
import xascraper.modules.ay.ayScrape as ays
import xascraper.modules.artstation.asScrape as ass
import xascraper.modules.tumblr.tumblrScrape as tus
import xascraper.modules.patreon.patreonScrape as pts
import xascraper.modules.yiff_party.yiff_scrape as yps

from settings import settings
import cherrypy


log = logging.getLogger("Main.Runtime")

class Nopper():
	pluginName = "Nop Job"
	def __init__(self):
		self.log = logging.getLogger("Main.Nop-Job")

	def go(self, *args, **kwargs):
		self.log.info("Empty job looping!")


def check_keys(kl):
	for keyn in kl:
		if not keyn in settings:
			raise RuntimeError("You're missing the setting parameters for the site "
				+ "'%s'. Check if you need to update your settings due to added scrapers."
				 % (keyn, ))


check_keys(["fa", "hf", "wy", "ib", "px", "sf","pat", "da", "ng", "ay", "as", "yp","tum"])



JOBS = [
	(fas.GetFA,      settings[ "fa"]["runInterval"],  "fa", False),
	(hfs.GetHF,      settings[ "hf"]["runInterval"],  "hf", False),
	(wys.GetWy,      settings[ "wy"]["runInterval"],  "wy", False),
	(ibs.GetIb,      settings[ "ib"]["runInterval"],  "ib", False),
	(pxs.GetPX,      settings[ "px"]["runInterval"],  "px", False),
	(sfs.GetSf,      settings[ "sf"]["runInterval"],  "sf", False),
	(pts.GetPatreon, settings["pat"]["runInterval"], "pat", False),
	# (Nopper,                                     30, "nop", False),
	(das.GetDA,      settings[ "da"]["runInterval"],  "da", False),
	(ngs.GetNg,      settings[ "ng"]["runInterval"],  "ng", False),
]


JOBS_DISABLED = [
	(ays.GetAy,      settings[ "ay"]["runInterval"],  "ay", False),
	(ass.GetAs,      settings[ "as"]["runInterval"],  "as", False),
	(yps.GetYp,      settings[ "yp"]["runInterval"],  "yp", False),
	(tus.GetTumblr,  settings["tum"]["runInterval"], "tum", False),
]

# Yeah, this has to be after the job init. Sigh.
import xascraper


def runScraper(scraper_class, managed_namespace):
	log.info("Scheduler executing class: %s", scraper_class)
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

	log.info("Stopping server.")
	cherrypy.engine.exit()
	log.info("Server stopped")


def scheduleJobs(sched, managedNamespace):

	# start = datetime.datetime.now() + datetime.timedelta(minutes=1)
	for scraperClass, interval, name in JOBS:
		# log.info(scraperClass, interval)
		sched.add_job(runScraper,
				trigger            = 'interval',
				seconds            = interval,
				start_date         = '2014-1-4 0:00:00',
				name               = name,
				args               = (scraperClass, managedNamespace,),
				coalesce           = True,
				max_instances      = 1,
				misfire_grace_time = 60 * 60 * 2,
			)
		# sched.add_job(runScraper, trigger='interval', seconds=interval, start_date=start, name=name, args=(scraperClass, managedNamespace,))
		# start = start  + datetime.timedelta(minutes=60)
	# sched.add_interval_job(printWat, seconds=10, start_date='2014-1-1 01:00')

JOB_MAP = {
		apscheduler.events.EVENT_SCHEDULER_STARTED  : "EVENT_SCHEDULER_STARTED",
		apscheduler.events.EVENT_SCHEDULER_SHUTDOWN : "EVENT_SCHEDULER_SHUTDOWN",
		apscheduler.events.EVENT_SCHEDULER_PAUSED   : "EVENT_SCHEDULER_PAUSED",
		apscheduler.events.EVENT_SCHEDULER_RESUMED  : "EVENT_SCHEDULER_RESUMED",
		apscheduler.events.EVENT_EXECUTOR_ADDED     : "EVENT_EXECUTOR_ADDED",
		apscheduler.events.EVENT_EXECUTOR_REMOVED   : "EVENT_EXECUTOR_REMOVED",
		apscheduler.events.EVENT_JOBSTORE_ADDED     : "EVENT_JOBSTORE_ADDED",
		apscheduler.events.EVENT_JOBSTORE_REMOVED   : "EVENT_JOBSTORE_REMOVED",
		apscheduler.events.EVENT_ALL_JOBS_REMOVED   : "EVENT_ALL_JOBS_REMOVED",
		apscheduler.events.EVENT_JOB_ADDED          : "EVENT_JOB_ADDED",
		apscheduler.events.EVENT_JOB_REMOVED        : "EVENT_JOB_REMOVED",
		apscheduler.events.EVENT_JOB_MODIFIED       : "EVENT_JOB_MODIFIED",
		apscheduler.events.EVENT_JOB_SUBMITTED      : "EVENT_JOB_SUBMITTED",
		apscheduler.events.EVENT_JOB_MAX_INSTANCES  : "EVENT_JOB_MAX_INSTANCES",
		apscheduler.events.EVENT_JOB_EXECUTED       : "EVENT_JOB_EXECUTED",
		apscheduler.events.EVENT_JOB_ERROR          : "EVENT_JOB_ERROR",
		apscheduler.events.EVENT_JOB_MISSED         : "EVENT_JOB_MISSED",
		apscheduler.events.EVENT_ALL                : "EVENT_ALL",
	}

def job_evt_listener(event):
	if event.exception:
		log.info('Job crashed: %s', event.job_id)
		log.info('Traceback: %s', event.traceback)

	else:

		log.info('Job event code: %s, job: %s', JOB_MAP[event.code], event.job_id)

def go(managedNamespace):
	log.info("Go()")


	resetter = xascraper.status_monitor.StatusResetter()
	resetter.resetRunState()

	# statusMgr = manage.statusDbManager.StatusResource()
	managedNamespace.run = True
	managedNamespace.serverRun = True

	server_process = multiprocessing.Process(target=serverProcess, args=(managedNamespace,))
	if "debug" in sys.argv:
		log.info("Not starting scheduler due to debug mode!")
		sched = None
	else:
		sched = BackgroundScheduler({
				'apscheduler.jobstores.default': {
					'type': 'memory'
				},
				'apscheduler.executors.default': {
					'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
					'max_workers'                              : 5
				},
				'apscheduler.job_defaults.coalesce'            : True,
				'apscheduler.job_defaults.max_instances'       : 1,
				'apscheduler.job_defaults.misfire_grace_time ' : 60 * 60 * 2,
			})


		logging.getLogger('apscheduler').setLevel(logging.DEBUG)
		sched.add_listener(job_evt_listener,
				apscheduler.events.EVENT_JOB_EXECUTED |
				apscheduler.events.EVENT_JOB_ERROR    |
				apscheduler.events.EVENT_JOB_MISSED   |
				apscheduler.events.EVENT_JOB_MAX_INSTANCES
			)
		scheduleJobs(sched, managedNamespace)
		sched.start()
		log.info("Scheduler is running!")

	log.info("Launching server process")
	server_process.start()
	loopCtr = 0

	log.info("Entering idle loop.")
	while managedNamespace.run:
		time.sleep(0.1)
		# if loopCtr % 100 == 0:
		# 	for job in sched.get_jobs():
		# 		print("Job: ", job.name, job.next_run_time.timestamp())
		# 		# statusMgr.updateNextRunTime(job.name, job.next_run_time.timestamp())
		loopCtr += 1

	if sched:
		sched.shutdown()
	log.info("Joining on web thread.")
	server_process.join()

def mgr_init():
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	log.info('initialized manager')

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		flags.namespace.serverRun = False
		log.info("Telling threads to stop")
	else:
		log.info("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

if __name__ == "__main__":

	manager = multiprocessing.managers.SyncManager()
	manager.start(mgr_init)
	flags.namespace = manager.Namespace()

	signal.signal(signal.SIGINT, signal_handler)
	logSetup.initLogging()
	go(flags.namespace)

	manager.shutdown()
