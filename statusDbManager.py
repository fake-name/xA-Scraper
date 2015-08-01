
#pylint: disable-msg=F0401, W0142

from settings import settings

import logging
import psycopg2
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
		ret = cur.execute('''
				SELECT table_name
				FROM information_schema.tables
				WHERE table_schema='public'
				ORDER BY table_schema,table_name;
			''')

		rets = cur.fetchall()
		tables = [item for sublist in rets for item in sublist]
		print("rets:", rets)
		print("tables:", tables)

		if not rets or not "statusdb" in tables:   # If the DB doesn't exist, set it up.
			cur = self.conn.cursor()
			self.log.info("Need to setup initial suceeded page database....")
			cur.execute('''CREATE TABLE statusdb (
												id          serial primary key,
												siteName    text NOT NULL,
												sectionName text NOT NULL,
												statusText  text,
												UNIQUE(siteName, sectionName))''')

			cur.execute('''CREATE INDEX statusDb_site_section_index ON statusdb (siteName, sectionName)''')

			cur.execute("commit")
			self.log.info("Status database created")


	def openDB(self):
		self.log.info("StatusManager Opening DB...")

		self.conn = psycopg2.connect(
			database = settings["postgres"]['database'],
			user     = settings["postgres"]['username'],
			password = settings["postgres"]['password'],
			host     = settings["postgres"]['address']
			)

		# self.log.info("DB Path = %s", self.dbPath)
		# self.conn = sqlite3.connect(self.dbPath, check_same_thread=False)
		# self.log.info("DB opened")


		# self.log.info("DB opened. Activating 'wal' mode")
		# rets = self.conn.execute('''PRAGMA journal_mode=wal;''')
		# # rets = self.conn.execute('''PRAGMA locking_mode=EXCLUSIVE;''')
		# rets = rets.fetchall()

		# self.log.info("PRAGMA return value = %s", rets)
		self.checkInitStatusDatabase()

	def updateValue(self, sitename, key, value):
		cur = self.conn.cursor()
		cur.execute("""SELECT id FROM statusdb WHERE sitename=%s AND sectionName=%s;""", (sitename, key))
		ret = cur.fetchone()
		if ret and ret[0]:
			cur.execute("""UPDATE statusdb SET statusText=%s WHERE id=%s""", (value, ret[0]))
		else:
			cur.execute('''INSERT INTO statusdb (siteName, sectionName, statusText) VALUES (%s, %s, %s);''', (sitename, key, value))


	def updateNextRunTime(self, name, timestamp):
		self.updateValue(name, "nextRun", timestamp)
		# cur = self.conn.cursor()
		# cur.execute("""SELECT id FROM statusdb WHERE sitename=%s AND sectionName=%s;""", ())
		# cur.execute('''INSERT INTO statusdb (siteName, sectionName, statusText) VALUES (%s, 'nextRun', %s);''', (name, timestamp))
		# cur.execute("commit")


	def updateLastRunStartTime(self, name, timestamp):
		self.updateValue(name, "prevRun", timestamp)
		# cur = self.conn.cursor()
		# cur.execute('''INSERT INTO statusdb (siteName, sectionName, statusText) VALUES (%s, 'prevRun', %s);''', (name, timestamp))
		# cur.execute("commit")

	def updateLastRunDuration(self, name, timeDelta):
		self.updateValue(name, "prevRunTime", timeDelta)
		# cur = self.conn.cursor()
		# cur.execute('''INSERT INTO statusdb (siteName, sectionName, statusText) VALUES (%s, 'prevRunTime', %s);''', (name, timeDelta))
		# cur.execute("commit")


	def updateRunningStatus(self, name, state):
		self.updateValue(name, "isRunning", state)
		# cur = self.conn.cursor()
		# cur.execute('''INSERT INTO statusdb (siteName, sectionName, statusText) VALUES (%s, 'isRunning', %s);''', (name, state))
		# cur.execute("commit")



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
