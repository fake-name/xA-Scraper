
#pylint: disable-msg=F0401, W0142


import logging
import psycopg2
import urllib.parse
import traceback

from settings import settings

class TumblrFeedImporter(object):

	log = logging.getLogger("Main.TumblrFeedImporter")

	def __init__(self):
		self.openDB()

	def __del__(self):
		self.closeDB()


	def checkInitStatusDatabase(self):

		cur = self.tt_conn.cursor()
		ret = cur.execute('''
				SELECT cat_id, feed_url
				FROM ttrss_feeds
				ORDER BY cat_id
			''')

		rets = cur.fetchall()

		tables = [{"id" : gid, "url" : url} for gid, url in rets]
		tables = [tmp for tmp in tables if 'tumblr' in tmp['url'].lower()]

		# magic constants for my db.
		tables = [tmp for tmp in tables if tmp['id'] in [16, 18]]

		for tdict in tables:

			self.insertFromUrl(tdict['url'])

	def insertFromUrl(self, url):
		url = urllib.parse.urlsplit(url)
		assert url.path.startswith("/rss")
		assert url.netloc.endswith("tumblr.com")

		aname = url.netloc.rsplit(".", 2)[0]

		self.checkInsertName("tum", aname)

	def checkInsertName(self, site, name):
		cur = self.main_conn.cursor()

		ret = cur.execute("SELECT * FROM %s WHERE siteName=%%s AND artistName=%%s;" % settings["dbConf"]["namesDb"], (site, name))
		have = cur.fetchall()

		if have:
			return

		self.log.info("New tumblr artist name: %s", name)
		cur.execute("INSERT INTO %s (siteName, artistName) VALUES (%%s, %%s);" % settings["dbConf"]["namesDb"], (site, name))
		cur.execute("COMMIT")

	def openDB(self):
		self.log.info("StatusManager Opening DB...")

		self.main_conn = psycopg2.connect(
			database = settings["postgres"]['database'],
			user     = settings["postgres"]['username'],
			password = settings["postgres"]['password'],
			host     = settings["postgres"]['address']
			)

		self.tt_conn = psycopg2.connect(
			database = settings["postgres"]['import_db'],
			user     = settings["postgres"]['import_db_user'],
			password = settings["postgres"]['import_db_pass'],
			host     = settings["postgres"]['address']
			)

	def closeDB(self):
		self.log.info("Closing DB...",)
		try:
			self.main_conn.close()
		except:
			self.log.error("wat")
			self.log.error(traceback.format_exc())

		try:
			self.tt_conn.close()
		except:
			self.log.error("wat")
			self.log.error(traceback.format_exc())

		self.log.info("done")

def go():
	wat = TumblrFeedImporter()
	wat.checkInitStatusDatabase()

if __name__ == "__main__":
	go()
