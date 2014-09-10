
import os
import os.path
import logging
import sqlite3
from settings import settings
import threading
from webFunctions import WebGetRobust
import abc

import hashlib
import mimetypes
mimetypes.init()

import statusDbManager


class PluginBase(metaclass=abc.ABCMeta):

	# Abstract class (must be subclassed)
	__metaclass__ = abc.ABCMeta



	@abc.abstractmethod
	def pluginName(self):
		return None



	def __init__(self):
		print("Starting up")
		self.loggers = {}
		self.lastLoggerIndex = 1


		self.log = logging.getLogger("Main.%s" % self.pluginName)
		self.wg = WebGetRobust()
		self.openDB()

		self.statusMgr = statusDbManager.StatusResource()
		print("Starting up?")

	def __del__(self):
		self.log.info("Unoading %s" % self.pluginName)
		self.closeDB()

	def openDB(self):
		self.log.info("Opening DB...",)

		# DB Connections are opened dynamically as needed by each thread.
		# See __getattribute__() for more information

		self.dbConnections = {}


		self.log.info("DB opened. Activating 'wal' mode, exclusive locking")
		rets = self.conn.execute('''PRAGMA journal_mode=wal;''')
		# rets = self.conn.execute('''PRAGMA locking_mode=EXCLUSIVE;''')
		rets = rets.fetchall()

		self.log.info("PRAGMA return value = %s", rets)

	def closeDB(self):
		self.log.info("Closing DB...",)
		self.conn.close()
		# I'm relying on the automatic destructor for deallocating most of the database handles,
		# since sqlite3 checks that calls on each connection is made from the same thread.
		# Annoying checking is annoying.
		self.log.info("DB Closed")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Messy hack to do log indirection so I can inject thread info into log statements, and give each thread it's own DB handle
	# (sqlite handles can't be shared between threads).
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __getattribute__(self, name):

		threadName = threading.current_thread().name
		if name == "log" and "Thread-" in threadName:
			if threadName not in self.loggers:
				self.loggers[threadName] = logging.getLogger("Main.%s.Thread-%d" % (self.pluginName, self.lastLoggerIndex))
				self.lastLoggerIndex += 1
			return self.loggers[threadName]


		elif name == "conn":
			if threadName not in self.dbConnections:
				self.dbConnections[threadName] = sqlite3.connect(settings["dbPath"], timeout=10)
			return self.dbConnections[threadName]


		else:
			return object.__getattribute__(self, name)



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# DB Crap!
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def checkInitPrimaryDb(self):

		cur = self.conn.cursor()
		ret = cur.execute('''SELECT name FROM sqlite_master WHERE type='table';''')
		rets = ret.fetchall()
		tables = [item for sublist in rets for item in sublist]

		if not rets or not settings["dbConf"]["successPagesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial suceeded page database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												pageUrl text NOT NULL,
												retreivalTime real NOT NULL,
												downloadPath text,
												itemPageContent text,
												itemPageTitle text,
												seqNum int,
												UNIQUE(siteName, artistName, pageUrl, seqNum) ON CONFLICT REPLACE)''' % settings["dbConf"]["successPagesDb"])

			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (retreivalTime)'''           % ("%s_time_index"          % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (pageUrl)'''                 % ("%s_pageurl_index"       % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (artistName)'''              % ("%s_artistname_index"    % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (siteName, retreivalTime)''' % ("%s_site_src_time_index" % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))

			self.conn.commit()
			self.log.info("Retreived page database created")

		if not rets or not settings["dbConf"]["retrevialTimeDB"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												retreivalTime real NOT NULL,
												UNIQUE(siteName, artistName) ON CONFLICT REPLACE)''' % settings["dbConf"]["retrevialTimeDB"])
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (artistName)'''     % ("%s_artistname_index" % settings["dbConf"]["retrevialTimeDB"], settings["dbConf"]["retrevialTimeDB"]))
			self.conn.commit()
			self.log.info("Retreival time database created")

		if not rets or not settings["dbConf"]["erroredPagesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												pageUrl text NOT NULL,
												retreivalTime real NOT NULL,
												UNIQUE(siteName, artistName, pageUrl) ON CONFLICT REPLACE)''' % settings["dbConf"]["erroredPagesDb"])
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (retreivalTime)'''  % ("%s_time_index"       % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (pageUrl)'''        % ("%s_pageurl_index"    % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (artistName)'''     % ("%s_artistname_index" % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			self.conn.commit()
			self.log.info("Error log database created")


		if not rets or not settings["dbConf"]["namesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			self.conn.execute('''CREATE TABLE %s (id INTEGER PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												uploadEh integer default 0,
												UNIQUE(siteName, artistName) ON CONFLICT REPLACE)''' % settings["dbConf"]["namesDb"])
			self.conn.execute('''CREATE INDEX IF NOT EXISTS %s ON %s (siteName, artistName)'''       % ("%s_index" % settings["dbConf"]["namesDb"]))
			self.conn.commit()
			self.log.info("Scanned Artist Name database created")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# FS Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getDownloadPath(self, siteSource, artist):
		return os.path.join(settings["dldCtntPath"], siteSource, artist)

	def getFilesForId(self, rowId):
		siteName, aName = self.getByRowId(rowId)
		filesPath = self.getDownloadPath(settings[siteName]["dlDirName"], aName)
		if not os.path.isdir(filesPath):
			raise ValueError("FilePath is invalid! %s" % filesPath)
		files = os.listdir(filesPath)
		ret = []
		for fileN in files:
			ret.append(os.path.join(filesPath, fileN))
		return ret

	def getImagesForId(self, rowId):

		baseFiles = self.getFilesForId(rowId)
		ret = []
		for fileN in baseFiles:
			mType, dummy_coding = mimetypes.guess_type(fileN)
			if mType and mType.startswith("image"):
				ret.append(fileN)
		return ret


	def getHashOfFile(self, filePath):
		hasher = hashlib.sha1()
		with open(filePath, "rb") as fp:
			fContents = fp.read()
		hasher.update(fContents)
		hexHash = hasher.hexdigest()
		return hexHash

	def _checkFileExists(self, filePath):
		# Return true if file exists
		# false if it does not
		# eventually will allow overwriting on command

		if os.path.exists(filePath):
			if os.path.getsize(filePath) > 100:
				return True
		return False

