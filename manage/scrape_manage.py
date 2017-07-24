

import flags
import os.path

import logSetup
from settings import settings

import signal
import time
import multiprocessing
import multiprocessing.managers
import sys


manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()
namespace.run = True

from main import JOBS
print(JOBS)

PLUGINS = {
		key : (cls_def, cls_def.pluginName)
	for cls_def, dummy_interval, key in JOBS
}

# PLUGINS = {

# 	'da'     : (GetDA,     "Deviant-Art"),
# 	'fa'     : (GetFA,     "Fur-Affinity"),
# 	'hf'     : (GetHF,     "Hentai Foundry"),
# 	'ib'     : (GetIb,     "Ink Bunny"),
# 	'px'     : (GetPX,     "Pixiv"),
# 	'sf'     : (GetSf,     "So Furry"),
# 	'tum'    : (GetTumblr, "Tumblr"),
# 	'wy'     : (GetWy,     "Weasyl"),

# }

def do_plugin(plg):
	plg.runScraper(namespace)
	# instance.go(ctrlNamespace=namespace)

def do_fetch(args):
	print("fetch args", args, type(args))
	if len(args) == 0:
		print("Fetching for all sites!")
		keys = list(PLUGINS.keys())
		keys.sort()
		for key in keys:
			plg, dummy_name = PLUGINS[key]
			do_plugin(plg)
	else:
		for plgname in args:
			if not plgname in PLUGINS:
				print("Error! Plugin short-name '%s' is not known!" % plgname)

		for plgname in args:
			plg, dummy_name = PLUGINS[plgname]
			do_plugin(plg)



def do_fetch_all():

	processes = [
			multiprocessing.Process(target=do_plugin, name='run-'+plg_name, args=(plg, ))
		for
			plg, plg_name in PLUGINS.values()
	]

	# Start all the plugins
	[tmp.start() for tmp in processes]

	while any([tmp.is_alive() for tmp in processes]):
		time.sleep(5)
		status = {tmp.name : tmp.is_alive() for tmp in processes}
		print("Plugin status: ", status)




def do_import(sitename, filename):
	if not sitename in PLUGINS:
		print("Error! Plugin short-name '%s' is not known!" % sitename)
		print("Showing help instead.")
		print("")
		print("")
		cli_help()
		return
	if not os.path.exists(filename):
		print("Error! File '%s' does not appear to exist!" % filename)
		print("Showing help instead.")
		print("")
		print("")
		cli_help()
		return
	if sitename.lower() == "px":
		print("Error!")
		print("Pixiv scraper uses a different mechanism for storing names.")
		print("(It uses your account favorites to determine who to scrape)")
		print("You cannot import names into it.")
		print("Showing help instead.")
		print("")
		print("")
		cli_help()
		return

	print("Import call: ", sitename, filename)

	with open(filename) as fp:
		names = fp.readlines()
		names = [name.strip() for name in names if name.strip()]
		if any([" " in name for name in names]):
			print("Error! A name with a space in it was found! That's not supported")
			print("for any plugin, at the moment! Something is wrong with the name")
			print("list file!")
			return
		print("Found %s names to insert into DB!" % len(names))
	conn = get_db_conn()
	cur = conn.cursor()
	for name in names:
		add_name(cur, sitename, name)
	cur.execute("COMMIT;")


