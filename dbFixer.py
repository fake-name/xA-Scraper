
import os
import os.path
import traceback
import concurrent.futures
import logging
import sqlite3
import flags
from settings import settings
import threading



class DbFixer(object):





	settingKeys  = [["da", "da"], ["fa", "fa"], ["hf", "hf"], ["px", "px"]]


	def __init__(self):
		print("Startomg up")
		self.openDB()
		print("Starting up?")
		self.loggers = {}
		self.lastLoggerIndex = 1

	def openDB(self):
		print("Opening DB...",)

		# DB Connections are opened dynamically as needed by each thread.
		# See __getattribute__() for more information

		self.conn = sqlite3.connect(settings["dbPath"], timeout=30)


		print("DB opened. Activating 'wal' mode")
		rets = self.conn.execute('''PRAGMA journal_mode=wal;''')
		rets = rets.fetchall()


	def moveItems(self):
		cur = self.conn.cursor()
		for key, shortName in self.settingKeys:
			print(key, shortName)
			for name in settings[key]["nameList"]:

				ret = cur.execute("INSERT INTO %s (siteName, artistName) VALUES (?, ?);" % settings["dbConf"]["namesDb"], (shortName, name))
				print(ret.fetchall())
			self.conn.commit()

			# dbName = self.daArtistTableName % name.lower()
			# if self.tableExists(dbName.rstrip("[]").lstrip("[]")):
			# 	ret = self.conn.execute("SELECT * FROM %s;" % dbName)
			# 	rets = ret.fetchall()
			# 	self.insertInto(settings["da"]["successPagesDb"], name, rets, dbName)
			# else:
			# 	print("Table `%s` does not exist" % dbName)
	def printNames(self, site):
		cur = self.conn.cursor()

		ret = cur.execute("SELECT artistName FROM %s WHERE siteName=?;" % settings["dbConf"]["namesDb"], (site, ))
		links = [link[0] for link in ret.fetchall()]
		return links

	def vacuumDb(self):
		print("Enabling auto-vacuum and vacuuming DB")
		self.conn.execute("PRAGMA auto_vacuum=FULL;")
		self.conn.execute("VACUUM")
		self.conn.commit()

	def fixPaths(self, badPrefix):
		cur = self.conn.cursor()
		loops = 0
		ret = cur.execute("SELECT id, downloadPath FROM %s;" % settings["dbConf"]["successPagesDb"])
		for idN, pathN in ret.fetchall():
			if badPrefix in pathN:
				new = os.path.relpath(pathN, badPrefix)
				cur.execute("UPDATE %s SET downloadPath=? WHERE id=?;" % settings["dbConf"]["successPagesDb"], (new, idN))
			loops += 1
			if loops % 1000 == 0:
				print("Loop", loops)
		print("Complete")
		self.conn.commit()

	def addColumn(self):
		cur = self.conn.cursor()
		ret = cur.execute("ALTER TABLE %s ADD COLUMN itemPageTitle text;" % settings["dbConf"]["successPagesDb"])
		print(ret.fetchall())
		self.conn.commit()

	def lowerCaseNames(self):
		cur = self.conn.cursor()

		ret = cur.execute('SELECT id, siteName, artistName FROM %s;' % settings["dbConf"]["namesDb"])
		rets = ret.fetchall()
		for uId, siteName, name in rets:
			if name != name.lower():
				print(uId, siteName, name)
				cur.execute("UPDATE %s SET artistName=? WHERE id=?" % settings["dbConf"]["namesDb"], (name.lower(), uId))
		self.conn.commit()

	def removeNonExistantItems(self):
		cur = self.conn.cursor()

		ret = cur.execute('SELECT id, downloadPath FROM %s;' % settings["dbConf"]["successPagesDb"])
		rets = ret.fetchall()
		loops = 0
		for uId, downloadPath in rets:
			fqPath = os.path.join(settings["dldCtntPath"], downloadPath)
			if not os.path.exists(fqPath):
				print(fqPath)
				cur.execute("""DELETE FROM %s WHERE id=?""" % settings["dbConf"]["successPagesDb"], (uId, ))

			loops += 1
			if loops % 5000 == 0:
				print("Loops = ", loops)
		self.conn.commit()

if __name__ == "__main__":
	dbF = DbFixer()

	# dbF.moveItems()
	# print(dbF.printNames("da"))
	# dbF.vacuumDb()
	# dbF.fixPaths("/Content/")
	# dbF.addColumn()
	# dbF.lowerCaseNames()
	# dbF.conn.execute("DROP TABLE px_retrieved_pages;")
	# dbF.conn.commit()

	# dbF.moveItems()

	# dbF.printDbStructure()

	dbF.removeNonExistantItems()

	# for artist in settings["da"]["nameList"]:
	# 	dbF.fixDbStructure("da_fetch_artist_%s", artist)
	# for artist in settings["da"]["nameList"]:
	# 	dbF.fixDbStructure("fa_fetch_artist_%s", artist)
