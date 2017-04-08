
import os
import os.path
import logging
import psycopg2
from settings import settings
import threading
from webFunctions import WebGetRobust
import abc

import hashlib
import mimetypes
mimetypes.init()

import manage.statusDbManager


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

		self.statusMgr = manage.statusDbManager.StatusResource()
		print("Starting up?")

	def __del__(self):
		self.log.info("Unoading %s" % self.pluginName)
		self.closeDB()

	def openDB(self):
		self.log.info("Opening DB...",)

		# DB Connections are opened dynamically as needed by each thread.
		# See __getattribute__() for more information

		self.dbConnections = {}


		self.conn = psycopg2.connect(
			database = settings["postgres"]['database'],
			user     = settings["postgres"]['username'],
			password = settings["postgres"]['password'],
			host     = settings["postgres"]['address']
			)


		# self.log.info("DB opened. Activating 'wal' mode, exclusive locking")
		# rets = self.conn.execute('''PRAGMA journal_mode=wal;''')
		# # rets = self.conn.execute('''PRAGMA locking_mode=EXCLUSIVE;''')
		# rets = rets.fetchall()

		# self.log.info("PRAGMA return value = %s", rets)

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
				self.dbConnections[threadName] = psycopg2.connect(
						database = settings["postgres"]['database'],
						user     = settings["postgres"]['username'],
						password = settings["postgres"]['password'],
						host     = settings["postgres"]['address']
						)
			return self.dbConnections[threadName]


		else:
			return object.__getattribute__(self, name)



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# DB Crap!
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def checkInitPrimaryDb(self):

		cur = self.conn.cursor()
		ret = cur.execute('''
				SELECT table_name
				FROM information_schema.tables
				WHERE table_schema='public'
				ORDER BY table_schema,table_name;
			''')

		rets = cur.fetchall()

		tables = [item for sublist in rets for item in sublist]

		cur = self.conn.cursor()
		if not rets or not settings["dbConf"]["successPagesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial suceeded page database....")
			cur.execute('''CREATE TABLE %s (
												id SERIAL PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												pageUrl text NOT NULL,
												retreivalTime real NOT NULL,
												downloadPath text,
												itemPageContent text,
												itemPageTitle text,
												seqNum int,
												UNIQUE(siteName, artistName, pageUrl, seqNum))''' % settings["dbConf"]["successPagesDb"])

			cur.execute('''CREATE INDEX %s ON %s (retreivalTime)'''           % ("%s_time_index"          % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			cur.execute('''CREATE INDEX %s ON %s (pageUrl)'''                 % ("%s_pageurl_index"       % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			cur.execute('''CREATE INDEX %s ON %s (artistName)'''              % ("%s_artistname_index"    % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))
			cur.execute('''CREATE INDEX %s ON %s (siteName, retreivalTime)''' % ("%s_site_src_time_index" % settings["dbConf"]["successPagesDb"], settings["dbConf"]["successPagesDb"]))

			cur.execute("commit")
			self.log.info("Retreived page database created")

		if not rets or not settings["dbConf"]["retrevialTimeDB"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			cur.execute('''CREATE TABLE %s (id SERIAL PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												retreivalTime real NOT NULL,
												UNIQUE(siteName, artistName))''' % settings["dbConf"]["retrevialTimeDB"])
			cur.execute('''CREATE INDEX %s ON %s (artistName)'''     % ("%s_artistname_index" % settings["dbConf"]["retrevialTimeDB"], settings["dbConf"]["retrevialTimeDB"]))
			cur.execute("commit")
			self.log.info("Retreival time database created")

		if not rets or not settings["dbConf"]["erroredPagesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			cur.execute('''CREATE TABLE %s (id SERIAL PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												pageUrl text NOT NULL,
												retreivalTime real NOT NULL,
												UNIQUE(siteName, artistName, pageUrl))''' % settings["dbConf"]["erroredPagesDb"])
			cur.execute('''CREATE INDEX %s ON %s (retreivalTime)'''  % ("%s_time_index"       % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			cur.execute('''CREATE INDEX %s ON %s (pageUrl)'''        % ("%s_pageurl_index"    % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			cur.execute('''CREATE INDEX %s ON %s (artistName)'''     % ("%s_artistname_index" % settings["dbConf"]["erroredPagesDb"], settings["dbConf"]["erroredPagesDb"]))
			cur.execute("commit")
			self.log.info("Error log database created")


		if not rets or not settings["dbConf"]["namesDb"] in tables:   # If the DB doesn't exist, set it up.
			self.log.info("Need to setup initial retreival time database....")
			cur.execute('''CREATE TABLE %s (id SERIAL PRIMARY KEY,
												siteName text NOT NULL,
												artistName text NOT NULL,
												uploadEh integer default 0,
												lastFetched double precision default 0,
												UNIQUE(siteName, artistName))''' % settings["dbConf"]["namesDb"])
			cur.execute('''CREATE INDEX %s ON %s (siteName, artistName)'''       % ("%s_index" % settings["dbConf"]["namesDb"], settings["dbConf"]["namesDb"]))
			cur.execute("commit")
			self.log.info("Scanned Artist Name database created")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# FS Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getDownloadPath(self, siteSource, artist):
		return os.path.join(settings["dldCtntPath"], siteSource, artist)

	def getFilesForId(self, rowId):
		siteName, aName = self.getByRowId(rowId)
		filesPath = self.getDownloadPath(settings[siteName]["dlDirName"], aName.lower())
		if not os.path.isdir(filesPath):
			raise ValueError("FilePath is invalid! %s" % filesPath)
		files = os.listdir(filesPath)
		ret = []
		for fileN in files:
			ret.append(os.path.join(filesPath, fileN))

		ret.sort()
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

