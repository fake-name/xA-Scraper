
import sys

import logSetup

from . import statusDbManager
from . import ttrssImport

def print_help():
	print()
	print("Manager interface")
	print("Options")
	print()
	print("	'rss-import'")
	print("		Import tumblr feeds from a ttrss database instance.")

def one_arg_go(command):
	if command == "rss-import":
		ttrssImport.go()

def two_arg_go(command, param):
	pass

def go():

	if len(sys.argv) == 1:
		print("No arguments! Cannot do anything!")
		print_help()
		return
	elif len(sys.argv) == 2:
		one_arg_go(sys.argv[1])
	elif len(sys.argv) == 3:
		two_arg_go(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
	logSetup.initLogging()
	go()

