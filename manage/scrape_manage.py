
from plugins.scrapers.da.daScrape import GetDA
from plugins.scrapers.px.pxScrape import GetPX
from plugins.scrapers.hf.hfScrape import GetHF
from plugins.scrapers.fa.faScrape import GetFA
from plugins.scrapers.sf.sfScrape import GetSf
from plugins.scrapers.ib.ibScrape import GetIb
from plugins.scrapers.wy.wyScrape import GetWy
from plugins.scrapers.tumblr.tumblrScrape import GetTumblr

import flags
import psycopg2
import os.path

import logSetup
from settings import settings

import signal
import multiprocessing.managers
import sys


manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()
namespace.run = True


PLUGINS = {

	'da'     : (GetDA,     "Deviant-Art"),
	'fa'     : (GetFA,     "Fur-Affinity"),
	'hf'     : (GetHF,     "Hentai Foundry"),
	'ib'     : (GetIb,     "Ink Bunny"),
	'px'     : (GetPX,     "Pixiv"),
	'sf'     : (GetSf,     "So Furry"),
	'tum'    : (GetTumblr, "Tumblr"),
	'wy'     : (GetWy,     "Weasyl"),

}

def do_plugin(plg):
	instance = plg()
	instance.go(ctrlNamespace=namespace)

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


def get_db_conn():

	conn = psycopg2.connect(
		database = settings["postgres"]['database'],
		user     = settings["postgres"]['username'],
		password = settings["postgres"]['password'],
		host     = settings["postgres"]['address']
		)
	return conn

def add_name(cur, site, name):
	pass

	ret = cur.execute("SELECT * FROM %s WHERE siteName=%%s AND artistName=%%s;" % settings["dbConf"]["namesDb"], (site, name))
	have = cur.fetchall()
	if have:
		return
	else:
		print("New name:", name)
		cur.execute("INSERT INTO %s (siteName, artistName) VALUES (%%s, %%s);" % settings["dbConf"]["namesDb"], (site, name))

	# self.conn.commit()

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


