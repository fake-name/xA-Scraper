
import time

import sys
import signal
import multiprocessing
import multiprocessing.managers
import logging
import logSetup


# Shut up fucking annoying psycopg2 vomit every exec.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='psycopg2')


import xascraper.status_monitor

import apscheduler.events
from apscheduler.schedulers.background import BackgroundScheduler

from settings import settings
import cherrypy
import flags


log = logging.getLogger("Main.Runtime")

import plugins

# Yeah, this has to be after the job init. Sigh.
import xascraper


def runScraper(scraper_class, managed_namespace):
	log.info("Scheduler executing class: %s", scraper_class)
	instance = scraper_class()
	instance.go(ctrlNamespace=managed_namespace)


def scheduleJobs(sched, managedNamespace):

	# start = datetime.datetime.now() + datetime.timedelta(minutes=1)
	for scraperClass, interval, name in plugins.JOBS:
		log.info("Scheduling %s to run every %s hours.", scraperClass, interval / (60 * 60))
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
	if hasattr(event, "exception") and event.exception:
		log.info('Job crashed: %s', event.job_id)
		log.info('Traceback: %s', event.traceback)
	else:
		log.info('Job event code: %s, job: %s', JOB_MAP[event.code], event.job_id)

def go(managedNamespace):
	log.info("Go()")


	resetter = xascraper.status_monitor.StatusResetter()
	resetter.reset_all_plugins_run_state()

	# statusMgr = manage.statusDbManager.StatusResource()
	managedNamespace.run = True
	managedNamespace.serverRun = True

	if "debug" in sys.argv:
		log.info("Not starting scheduler due to debug mode!")
		sched = None
	else:

		aplogger = logging.getLogger('apscheduler')
		if aplogger.hasHandlers():
			aplogger.handlers.clear()

		aplogger.setLevel(logging.ERROR)

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

		sched.start()

		sched.add_listener(job_evt_listener,
				apscheduler.events.EVENT_JOB_EXECUTED |
				apscheduler.events.EVENT_JOB_ERROR    |
				apscheduler.events.EVENT_JOB_MISSED   |
				apscheduler.events.EVENT_JOB_MAX_INSTANCES
			)
		scheduleJobs(sched, managedNamespace)
		aplogger.setLevel(logging.DEBUG)
		log.info("Scheduler is running!")

	loopCtr = 0

	log.info("Entering idle loop.")
	while managedNamespace.run:
		time.sleep(0.1)
		# if loopCtr % 100 == 0:
		# 	for job in sched.get_jobs():
		# 		print("Job: ", job.name, job.next_run_time.timestamp() -time.time())
		# 		# statusMgr.updateNextRunTime(job.name, job.next_run_time.timestamp())
		# loopCtr += 1

	if sched:
		sched.shutdown()
	log.info("Joining on web thread.")

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
