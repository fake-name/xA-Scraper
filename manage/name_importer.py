
#pylint: disable-msg=F0401, W0142


import logging
import psycopg2
import urllib.parse
import traceback
import os

from rewrite import db
from rewrite import database
import rewrite.modules.tumblr.tumblrScrape

from .scrape_manage import PLUGINS
from . import cli_utils

from settings import settings


class NameImporter(rewrite.modules.tumblr.tumblrScrape.GetTumblr):

	log = logging.getLogger("Main.NameImporter")


	def update_from_tt_rss(self):
		self.open_ttrss_db()

		cur = self.tt_conn.cursor()
		cur.execute('''
				SELECT cat_id, feed_url
				FROM ttrss_feeds
				ORDER BY cat_id
			''')

		rets = cur.fetchall()

		tables = [{"id" : gid, "url" : url} for gid, url in rets]
		tables = [tmp for tmp in tables if 'tumblr' in tmp['url'].lower()]

		# magic constants for my db.
		tables = [tmp for tmp in tables if tmp['id'] in [16, 18]]

		self.log.info("Found %s items to insert", len(tables))

		for tdict in tables:
			self.insert_name_from_tumblr_url(tdict['url'])


		self.close_ttrss_db()

	def insert_name_from_tumblr_url(self, url):
		url = urllib.parse.urlsplit(url)
		assert url.path.startswith("/rss")
		assert url.netloc.endswith("tumblr.com")

		aname = url.netloc.rsplit(".", 2)[0]

		self.checkInsertName("tum", aname)

	def update_names_from_tumblr_followed(self):
		self.log.info("Updating artists from follows on tumblr.")
		following = self.t.following()
		self.log.info( "Following: %s artists on tumblr", len(following))
		for info in following["blogs"]:
			name = info["name"]
			self.checkInsertName("tum", name)


	def checkInsertName(self, site, name):
		have_item = db.session.query(database.ScrapeTargets)    \
			.filter(database.ScrapeTargets.site_name == site)   \
			.filter(database.ScrapeTargets.artist_name == name) \
			.scalar()

		if have_item:
			self.log.info("Have %s -> %s", site, name)
			db.session.commit()
			return

		self.log.info("Adding %s -> %s", site, name)
		new = database.ScrapeTargets(
			site_name   = site,
			artist_name = name,
			)

		db.session.add(new)
		db.session.commit()



	def open_ttrss_db(self):
		self.log.info("StatusManager Opening DB...")

		self.tt_conn = psycopg2.connect(
			database = settings["postgres"]['import_db'],
			user     = settings["postgres"]['import_db_user'],
			password = settings["postgres"]['import_db_pass'],
			host     = settings["postgres"]['address']
			)

	def close_ttrss_db(self):
		self.log.info("Closing DB...",)

		try:
			self.tt_conn.close()
		except:
			self.log.error("wat")
			self.log.error(traceback.format_exc())

		self.log.info("done")



	def import_names_from_file(self, sitename, filename):
		if not sitename in PLUGINS:
			print("Error! Plugin short-name '%s' is not known!" % sitename)
			print("Showing help instead.")
			print("")
			print("")
			cli_utils.print_help()
			return
		if not os.path.exists(filename):
			print("Error! File '%s' does not appear to exist!" % filename)
			print("Showing help instead.")
			print("")
			print("")
			cli_utils.print_help()
			return
		if sitename.lower() == "px":
			print("Error!")
			print("Pixiv scraper uses a different mechanism for storing names.")
			print("(It uses your account favorites to determine who to scrape)")
			print("You cannot import names into it.")
			print("Showing help instead.")
			print("")
			print("")
			cli_utils.print_help()
			return

		print("Import call: ", sitename, filename)

		with open(filename) as fp:
			names = fp.readlines()
			names = [name.strip() for name in names if name.strip()]

			comments = [tmp for tmp in names if tmp.startswith("#")]
			names = [tmp for tmp in names if not tmp.startswith("#")]

			if any([" " in name for name in names]):
				print("Error! A name with a space in it was found! That's not supported")
				print("for any plugin, at the moment! Something is wrong with the name")
				print("list file!")
				return
			print("Found %s names to insert into DB!" % len(names))
			print("%s lines that are commented out!" % len(comments))
		for name in names:
			self.checkInsertName(sitename, name)

