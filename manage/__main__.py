
import sys

import logSetup

from . import ttrssImport
from .scrape_manage import do_fetch_all
from .scrape_manage import do_fetch
from .scrape_manage import do_import
from .scrape_manage import PLUGINS

from manage import db_manage

def print_help():
	print()
	print("Manager interface")
	print("Options")
	print()
	print("	help")
	print("		print this message")
	print("	'rss-import'")
	print("		Import tumblr feeds from a ttrss database instance.")
	print("	'upgrade-db'")
	print("		Make any needed schema changes to the database, if needed.")
	print("	'name-clean'")
	print("		Checks and does some cleanup of the artist-names in the database.")
	print("	'db-misrelink-clean'")
	print("		Does release sanity checks on item URLs")
	print("	fetch [sitename]")
	print("		with no sitename, this executes all plugins in sequence.")
	print("		With a sitename, executes the named plugin.")
	print("	fetch-all")
	print("		Executes all plugins in parallel.")
	print("	import <sitename> <filename>")
	print("		Open a text file <filename>, and import the names from")
	print("		it into the monitored names database for site <sitename>.")
	print("		The file <filename> must be a simple text file with")
	print("		one artist name per-line.")
	print("		Note that this does not support pixiv names, due to the ")
	print("		different mechanism used for supporting pixiv namelist")
	print("		tracking.")

	print("")
	print("	Available plugins (sitename -> Human-Readable name):")
	for key, tup in PLUGINS.items():
		print("		{} -> {}".format(key.ljust(8), tup[1]))


def one_arg_go(command):
	if command == "rss-import":
		ttrssImport.go()
	if command == "fetch":
		do_fetch([])
	if command == "fetch-all":
		do_fetch_all()
	if command == 'name-clean':
		db_manage.db_name_clean()
	if command == 'db-misrelink-clean':
		db_manage.db_misrelink_clean()

def two_arg_go(command, param):

	if command == "fetch":
		do_fetch([param])


def three_arg_go(command, param_1, param_2):

	if command == "import":
		do_import(param_1, param_2)

def go():

	if len(sys.argv) == 1:
		print("No arguments! Cannot do anything!")
		print_help()
		return
	elif len(sys.argv) == 2:
		one_arg_go(sys.argv[1])
	elif len(sys.argv) == 3:
		two_arg_go(sys.argv[1], sys.argv[2])
	elif len(sys.argv) == 4:
		three_arg_go(sys.argv[1], sys.argv[2], sys.argv[3])

if __name__ == "__main__":
	logSetup.initLogging()
	go()

