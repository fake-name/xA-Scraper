
import sys

import logSetup
import multiprocessing
import flags
import signal
import logging


# Shut up fucking annoying psycopg2 vomit every exec.
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='psycopg2')

from . import name_importer

from manage import db_manage
from manage import scrape_manage

from . import cli_utils


def one_arg_go(command):
	if command == "rss-import":
		importer = name_importer.NameImporter()
		importer.update_from_tt_rss()

	elif command == "tumblr-import":
		importer = name_importer.NameImporter()
		importer.update_names_from_tumblr_followed()
	elif command == "fetch":
		scrape_manage.do_fetch([])
	elif command == "fetch-all":
		scrape_manage.do_fetch_all()
	elif command == 'name-clean':
		db_manage.db_name_clean()
	elif command == 'db-misrelink-clean':
		db_manage.db_misrelink_clean()
	elif command == 'reset-run-state':
		db_manage.reset_run_state()
	elif command == 'reset-last-fetched-times':
		scrape_manage.reset_last_fetched_times()
	elif command == 'dump-json':
		db_manage.dump_item_meta()
	elif command == 'reset-missing':
		db_manage.reset_missing()
	else:
		cli_utils.print_help()


def two_arg_go(command, param):

	if command == "fetch":
		scrape_manage.do_fetch([param])

	elif command == 'reset-run-state':
		db_manage.reset_run_state(param)
	elif command == 'reset-last-fetched-times':
		scrape_manage.reset_last_fetched_times(param)
	else:
		cli_utils.print_help()

def three_arg_go(command, param_1, param_2):

	if command == "import":
		importer = name_importer.NameImporter()
		importer.import_names_from_file(param_1, param_2)

		db_manage.db_name_clean()
	elif command == "dump":
		db_manage.export_db_contents(to_path=param_1, site_name=param_2)

	else:
		cli_utils.print_help()


def mgr_init():
	print("Setup")
	signal.signal(signal.SIGINT, signal.SIG_IGN)

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	print('initialized manager')

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

def go():

	mgr_init()

	if len(sys.argv) == 1:
		print("No arguments! Cannot do anything!")
		cli_utils.print_help()
		return
	elif len(sys.argv) == 2:
		one_arg_go(sys.argv[1])
	elif len(sys.argv) == 3:
		two_arg_go(sys.argv[1], sys.argv[2])
	elif len(sys.argv) == 4:
		three_arg_go(sys.argv[1], sys.argv[2], sys.argv[3])

if __name__ == "__main__":
	# logSetup.initLogging(logLevel=logging.DEBUG)
	logSetup.initLogging()
	go()

