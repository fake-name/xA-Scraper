
import os
import os.path
import traceback
import concurrent.futures
import logging
import sqlite3
from settings import settings
import threading
import datetime
import time
import urllib.error
import abc
from settings import settings

from rewrite.modules import module_base

class ScraperBase(module_base.ModuleBase, metaclass=abc.ABCMeta):

	# Abstract class (must be subclassed)
	__metaclass__ = abc.ABCMeta

	def __init__(self):
		print("ScraperBase Init")
		self.dlBasePath = settings[self.settingsDictKey]["dlDirName"]
		self.targetShortName = settings[self.settingsDictKey]["shortName"]

		super().__init__()


	@abc.abstractmethod
	def settingsDictKey(self):
		return None


	ovwMode = "Check Files"

	numThreads = 5



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	@abc.abstractmethod
	def checkCookie(self):
		pass

	@abc.abstractmethod
	def getCookie(self):
		pass


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	@abc.abstractmethod
	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		pass


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	@abc.abstractmethod
	def _getTotalArtCount(self, artist):
		pass

	@abc.abstractmethod
	def _getItemsOnPage(self, inSoup):
		pass

	@abc.abstractmethod
	def _getGalleries(self, artist):
		pass

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# DB Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _artist_name_to_rid(self, aname):
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets.id)             \
				.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
				.filter(self.db.ScrapeTargets.artist_name == aname)              \
				.one()
			return res[0]



	# Fetch the previously retrieved item URLs from the database.
	def _getPreviouslyRetreived(self, artist):
		aid = self._artist_name_to_rid(artist)
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ArtItem.release_meta) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.all()

			return set([item for sublist in res for item in sublist])

	# Insert recently retreived items into the database
	def _updatePreviouslyRetreived(self, artist, pageUrl, fqDlPath, pageDesc="", pageTitle="", seqNum=0, filename=None):
		# Sqlite requires all arguments be at least tuples containing string.
		# Respin our list into a list of 1-tuples

		# print("DB Arg artist    = ", artist)
		# print("DB Arg pageUrl   = ", pageUrl)
		# print("DB Arg fqDlPath  = ", fqDlPath)
		# print("DB Arg pageDesc  = ", type(pageDesc))
		# print("DB Arg pageTitle = ", pageTitle)
		# print("DB Arg seqNum    = ", seqNum)

		# print("Inserting sequence: ", seqNum)

		aid = self._artist_name_to_rid(artist)


		with self.db.context_sess() as sess:

			row = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.release_meta == pageUrl) \
				.scalar()
			if not row:
				row = self.db.ArtItem(
						state        = 'complete',
						artist_id    = aid,
						release_meta = pageUrl,
						fetchtime    = datetime.datetime.now(),
						addtime      = datetime.datetime.now(),
						title        = pageTitle,
						content      = pageDesc,
					)
				sess.add(row)
				sess.flush()

			frow = sess.query(self.db.ArtFile) \
				.filter(self.db.ArtFile.item_id == row.id) \
				.filter(self.db.ArtFile.seqnum == seqNum) \
				.scalar()

			if frow:
				if frow.fspath != fqDlPath:
					self.log.error("Item already exists, but download path is changing?")
					self.log.error("Old path: '%s'", frow.fspath)
					self.log.error("New path: '%s'", fqDlPath)
			else:
				frow = self.db.ArtFile(
						item_id  = row.id,
						seqnum   = seqNum,
						filename = filename,
						fspath   = fqDlPath,
					)
				sess.add(frow)

			sess.commit()


	def _checkHaveUrl(self, artist, url):
		aid = self._artist_name_to_rid(artist)
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.release_meta == url) \
				.filter(self.db.ArtItem.state == 'complete') \
				.count()
			print("Res:", res)
			return res



	# Insert bad item into DB
	def _updateUnableToRetrieve(self, artist, errUrl):

		aid = self._artist_name_to_rid(artist)


		with self.db.context_sess() as sess:

			row = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.release_meta == errUrl) \
				.scalar()
			if not row:
				row = self.db.ArtItem(
						state        = 'error',
						artist_id    = aid,
						release_meta = errUrl,
						fetchtime    = datetime.datetime.now(),
						addtime      = datetime.datetime.now(),
					)
				sess.add(row)
				sess.commit()



		# Sqlite requires all arguments be at least tuples containing string.
		# Respin our list into a list of 1-tuples
		# self.log.error("Inserting errored page %s for artist %s into %s", errUrl, artist, settings["dbConf"]["erroredPagesDb"])

		# cur = self.conn.cursor()

		# cur.execute("SELECT id FROM %s WHERE sitename=%%s AND artistname=%%s AND pageurl=%%s;" % settings["dbConf"]["erroredPagesDb"], (self.targetShortName, artist, errUrl))
		# have = cur.fetchone()
		# if have and have[0]:
		# 	cur.execute("UPDATE %s SET retreivalTime=%%s WHERE id=%%s;" % settings["dbConf"]["erroredPagesDb"], (time.time(), have[0]))
		# else:
		# 	cur.execute("INSERT INTO %s (siteName, artistName, pageUrl, retreivalTime) VALUES (%%s, %%s, %%s, %%s);" % settings["dbConf"]["erroredPagesDb"], (self.targetShortName, artist, errUrl, time.time()))
		# # dummy_rets = cur.fetchall()
		# cur.execute("commit")
		# self.log.info("DB Updated")

	def _updateLastFetched(self, artist):

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets) \
				.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
				.filter(self.db.ScrapeTargets.artist_name == artist) \
				.one()
			res.last_fetched = datetime.datetime.now()
			sess.commit()


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# FS Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	# Prep download dir (if needed)
	def setupDir(self, artist):

		dirPath = self.getDownloadPath(self.dlBasePath, artist)
		if not os.path.exists(dirPath):
			try:
				os.makedirs(dirPath)
			except:
				self.log.error("Cannot Make working directory %s/. Do you have write Permissions?", dirPath)
				raise
		if os.path.isfile(dirPath):
			raise IOError("Download path exists, and is a file. Wat")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets) \
				.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
				.all()

			ret = [(row.id, row.artist_name) for row in res]
			sess.commit()

		return ret

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Threading and task management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getArtist(self, artist, ctrlNamespace):
		if ctrlNamespace.run == False:
			self.log.warning("Exiting early from %s due to run flag being unset", artist)
			return True

		artist = artist.lower() # Fuck you case-sensitive filesystem
		dlPathBase = self.getDownloadPath(self.dlBasePath, artist)

		# return True

		try:
			self.log.info("GetArtist - %s", artist)
			self.setupDir(artist)

			totalArt = self._getTotalArtCount(artist)
			artPages = self._getGalleries(artist)

			if totalArt is None:
				self.log.info("Site does not support total art counts. Found total gallery items %s", len(artPages))
			elif totalArt > len(artPages):
				self.log.warning("May be missing art? Total claimed art items from front-page = %s, total gallery items %s", totalArt, len(artPages))
			elif totalArt < len(artPages):
				self.log.warning("Too many art pages found? Total claimed art items from front-page = %s, total gallery items %s.", totalArt, len(artPages))
			else:
				self.log.info("Total claimed art items from front-page = %s, total gallery items %s", totalArt, len(artPages))

			oldArt = self._getPreviouslyRetreived(artist)
			newArt = artPages - oldArt
			self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

			while len(newArt) > 0:
				pageURL = newArt.pop()
				status = None
				try:
					ret = self._getArtPage(dlPathBase, pageURL, artist)
					if len(ret) == 2:
						status, fqDlPath = ret
						pageDesc = ""
						pageTitle = ""
					elif len(ret) == 4:
						status, fqDlPath, pageDesc, pageTitle = ret
					else:
						raise ValueError("Wat?")



					# Pull off the absolute path, so the DB is just the relative path within the content dir

				except urllib.error.URLError:  # WebGetRobust throws urlerrors
					self.log.error("Page Retrieval failed!")
					self.log.error("Source URL = '%s'", pageURL)
					self.log.error(traceback.format_exc())
				except:
					self.log.error("Unknown error in page retrieval!")
					self.log.error("Source URL = '%s'", pageURL)
					self.log.error(traceback.format_exc())
				finally:
					if status == "Succeeded" or status == "Exists":
						if isinstance(fqDlPath, list):
							seq = 0
							for item in fqDlPath:
								print(item)
								fqItem = os.path.relpath(item, settings["dldCtntPath"])
								self._updatePreviouslyRetreived(artist=artist, pageUrl=pageURL, fqDlPath=fqItem, pageDesc=pageDesc, pageTitle=pageTitle, seqNum=seq)
								seq += 1
						elif isinstance(fqDlPath, str):
							fqDlPath = os.path.relpath(fqDlPath, settings["dldCtntPath"])
							self._updatePreviouslyRetreived(artist=artist, pageUrl=pageURL, fqDlPath=fqDlPath, pageDesc=pageDesc, pageTitle=pageTitle, seqNum=0)
						elif fqDlPath == None:
							self._updatePreviouslyRetreived(artist=artist, pageUrl=pageURL, fqDlPath=None, pageDesc=pageDesc, pageTitle=pageTitle, seqNum=0)
						else:
							raise ValueError("Unknown type for received downloadpath")
					elif status == "Ignore":  # Used for compound pages (like Pixiv's manga pages), where the page has multiple sub-pages that are managed by the plugin
						self.log.info("Ignoring root URL, since it has child-pages.")
					else:
						self._updateUnableToRetrieve(artist, pageURL)

				self.log.info("Pages for %s remaining = %s", artist, len(newArt))
				if ctrlNamespace.run == False:
					break

			self._updateLastFetched(artist)
			self.log.info("Successfully retreived content for artist %s", artist)

			return False
		except:
			self.log.error("Exception when retreiving artist %s", artist)
			self.log.error("%s", traceback.format_exc())
			try:
				cur = self.conn.cursor()
				cur.execute("rollback;")
			except:
				print("Failed to roll-back")
				print(traceback.print_exc())
			return True


	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace == None:
			raise ValueError("You need to specify a namespace!")
		self.statusMgr.updateRunningStatus(self.settingsDictKey, True)
		startTime = time.time()
		self.statusMgr.updateLastRunStartTime(self.settingsDictKey, startTime)
		self.checkInitPrimaryDb()

		if not nameList:
			nameList = self.getNameList()

		haveCookie, dummy_message = self.checkCookie()
		if not haveCookie:
			self.log.info("Do not have login cookie. Retreiving one now.")
			cookieStatus = self.getCookie()
			self.log.info("Login attempt status = %s.", cookieStatus)

		haveCookie, dummy_message = self.checkCookie()
		if not haveCookie:
			self.log.critical("Failed to download cookie! Exiting!")
			return False


		errored = False

		# Farm out requests to the thread-pool
		with concurrent.futures.ThreadPoolExecutor(max_workers=self.numThreads) as executor:

			future_to_url = {}
			for aId, aName in nameList:
				future_to_url[executor.submit(self.getArtist, aName, ctrlNamespace)] = aName

			for future in concurrent.futures.as_completed(future_to_url):
				# aName = future_to_url[future]
				# res = future.result()
				errored  |= future.result()
				# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

		if errored:
			self.log.warn("Had errors!")

		self.statusMgr.updateRunningStatus(self.settingsDictKey, False)
		runTime = time.time()-startTime
		self.statusMgr.updateLastRunDuration(self.settingsDictKey, runTime)



	@classmethod
	def runScraper(cls, managedNamespace):
		instance = cls()
		instance.go(ctrlNamespace=managedNamespace)

