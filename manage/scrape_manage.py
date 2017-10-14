

import flags
import os.path

import logSetup
from settings import settings

import signal
import time
import multiprocessing
import multiprocessing.managers
import sys

from . import cli_utils

manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()
namespace.run = True

from main import JOBS

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




