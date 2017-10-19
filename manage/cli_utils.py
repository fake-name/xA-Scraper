
#pylint: disable-msg=F0401, W0142


import logging
import psycopg2
import urllib.parse
import traceback

from rewrite import db
from rewrite import database

from settings import settings

from main import JOBS

PLUGINS = {
		key : (cls_def, cls_def.pluginName)
	for cls_def, dummy_interval, key in JOBS
}

def print_help():
	print()
	print("Manager interface")
	print("Options")
	print()
	print("	help")
	print("		print this message")
	print("	reset-run-state")
	print("		reset the run-state monitor flags. This is normally done")
	print("		at start by main.py, but if you're using just the CLI fetch")
	print("		calls, you can do it manually too.")
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
	print("		Note: this will call `name-clean` after execution automatically.")

	print("")
	print("	Available plugins (sitename -> Human-Readable name):")
	for key, tup in PLUGINS.items():
		print("		{} -> {}".format(key.ljust(8), tup[1]))

