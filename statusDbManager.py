
#pylint: disable-msg=F0401, W0142

from settings import settings

import logging
import sqlite3
import traceback

class StatusResource(object):

	log = logging.getLogger("Main.StatusMgr")

	def __init__(self):
		self.dbPath = settings["dbPath"]

		self.openDB()

	def __del__(self):
		self.closeDB()


	def checkInitStatusDatabase(self):

		cur = self.conn.cursor()
		ret = cur.execute('''SELECT name FROM sqlite_master WHERE type='table';''')
		rets = ret.fetchall()
		tables = [item for sublist in rets for item in sublist]

		if not rets or not "statusDb" in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial suceeded page database....")
			self.conn.execute('''CREATE TABLE statusDb (siteName text NOT NULL,
												sectionName text NOT NULL,
												statusText text,
												UNIQUE(siteName, sectionName) ON CONFLICT REPLACE)''')

			self.conn.execute('''CREATE INDEX IF NOT EXISTS statusDb_site_section_index ON statusDb (siteName, sectionName)''')

			self.conn.commit()
			self.log.info("Status database created")


	def openDB(self):
		self.log.info("StatusManager Opening DB...")
		self.log.info("DB Path = %s", self.dbPath)
		self.conn = sqlite3.connect(self.dbPath, check_same_thread=False)
		self.log.info("DB opened")


		self.log.info("DB opened. Activating 'wal' mode")
		rets = self.conn.execute('''PRAGMA journal_mode=wal;''')
		# rets = self.conn.execute('''PRAGMA locking_mode=EXCLUSIVE;''')
		rets = rets.fetchall()

		self.log.info("PRAGMA return value = %s", rets)
		self.checkInitStatusDatabase()

	def updateNextRunTime(self, name, timestamp):
		cur = self.conn.cursor()
		cur.execute('''INSERT INTO statusDb (siteName, sectionName, statusText) VALUES (?, 'nextRun', ?);''', (name, timestamp))
		self.conn.commit()


	def updateLastRunStartTime(self, name, timestamp):
		cur = self.conn.cursor()
		cur.execute('''INSERT INTO statusDb (siteName, sectionName, statusText) VALUES (?, 'prevRun', ?);''', (name, timestamp))
		self.conn.commit()

	def updateLastRunDuration(self, name, timeDelta):
		cur = self.conn.cursor()
		cur.execute('''INSERT INTO statusDb (siteName, sectionName, statusText) VALUES (?, 'prevRunTime', ?);''', (name, timeDelta))
		self.conn.commit()


	def updateRunningStatus(self, name, state):
		cur = self.conn.cursor()
		cur.execute('''INSERT INTO statusDb (siteName, sectionName, statusText) VALUES (?, 'isRunning', ?);''', (name, state))
		self.conn.commit()



	def closeDB(self):
		self.log.info("Closing DB...",)
		try:
			self.conn.close()
		except:
			self.log.error("wat")
			self.log.error(traceback.format_exc())
		self.log.info("done")

def go():
	wat = StatusResource()
	print(wat)

if __name__ == "__main__":
	go()
