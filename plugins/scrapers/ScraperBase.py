
import os
import os.path
import traceback
import concurrent.futures
import logging
import sqlite3
from settings import settings
import threading
import time
import urllib.error
from webFunctions import WebGetRobust
import abc
from settings import settings

import statusDbManager
from plugins.PluginBase import PluginBase

import plugins.uploaders.eHentai.eHentaiUl


class ScraperBase(PluginBase, metaclass=abc.ABCMeta):

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


	# Fetch the previously retrieved item URLs from the database.
	def _getPreviouslyRetreived(self, artist):
		cur = self.conn.cursor()

		# cur.execute("SELECT (pageUrl) FROM %s WHERE siteName=? AND artistName=? AND itemPageContent IS NULL AND itemPageTitle IS NULL;" % settings["dbConf"]["successPagesDb"], (self.targetShortName, artist))
		cur.execute("SELECT (pageUrl) FROM %s WHERE siteName=%%s AND artistName=%%s;" % settings["dbConf"]["successPagesDb"], (self.targetShortName, artist))
		rets = cur.fetchall()
		self.log.info("Previously retreived %s items", len(rets))
		return set([item for sublist in rets for item in sublist])

	# Insert recently retreived items into the database
	def _updatePreviouslyRetreived(self, artist, pageUrl, fqDlPath, pageDesc="", pageTitle="", seqNum=0):
		# Sqlite requires all arguments be at least tuples containing string.
		# Respin our list into a list of 1-tuples

		# print("DB Arg artist    = ", artist)
		# print("DB Arg pageUrl   = ", pageUrl)
		# print("DB Arg fqDlPath  = ", fqDlPath)
		# print("DB Arg pageDesc  = ", type(pageDesc))
		# print("DB Arg pageTitle = ", pageTitle)
		# print("DB Arg seqNum    = ", seqNum)

		# print("Inserting sequence: ", seqNum)

		self.log.info("Inserting retrieved page %s into %s", pageUrl, settings["dbConf"]["successPagesDb"])

		cur = self.conn.cursor()
		cur.execute("""INSERT INTO {table}
		                     (siteName, artistName, pageUrl, retreivalTime, downloadPath, seqNum, itemPageContent, itemPageTitle)
		              VALUES
		                     (%s,        %s,         %s,      %s,            %s,           %s,     %s,              %s)
		              ;""".format(table=settings["dbConf"]["successPagesDb"]),
		                      (self.targetShortName, artist, pageUrl, time.time(), fqDlPath, seqNum, pageDesc,      pageTitle))
		# dummy_rets = cur.fetchall()

		# Delete from the failed database if it got put there in the past
		cur.execute("DELETE FROM %s WHERE siteName=%%s AND pageUrl=%%s AND artistName=%%s;" % settings["dbConf"]["erroredPagesDb"], (self.targetShortName, pageUrl, artist))
		# dummy_rets = cur.fetchall()

		self.log.info("DB Updated")
		cur.execute("commit")

	def _checkHaveUrl(self, url):
		cur = self.conn.cursor()

		cur.execute("SELECT COUNT(*) FROM %s WHERE pageUrl=%%s;" % settings["dbConf"]["successPagesDb"], (url, ))
		have = cur.fetchall()[0][0]
		return have


	# Insert bad item into DB
	def _updateUnableToRetrieve(self, artist, errUrl):
		# Sqlite requires all arguments be at least tuples containing string.
		# Respin our list into a list of 1-tuples
		self.log.error("Inserting errored page %s for artist %s into %s", errUrl, artist, settings["dbConf"]["erroredPagesDb"])

		cur = self.conn.cursor()

		cur.execute("SELECT id FROM %s WHERE sitename=%%s AND artistname=%%s AND pageurl=%%s;" % settings["dbConf"]["erroredPagesDb"], (self.targetShortName, artist, errUrl))
		have = cur.fetchone()
		if have and have[0]:
			cur.execute("UPDATE %s SET retreivalTime=%%s WHERE id=%%s;" % settings["dbConf"]["erroredPagesDb"], (time.time(), have[0]))
		else:
			cur.execute("INSERT INTO %s (siteName, artistName, pageUrl, retreivalTime) VALUES (%%s, %%s, %%s, %%s);" % settings["dbConf"]["erroredPagesDb"], (self.targetShortName, artist, errUrl, time.time()))
		# dummy_rets = cur.fetchall()
		cur.execute("commit")
		self.log.info("DB Updated")


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

		cur = self.conn.cursor()

		cur.execute("SELECT artistName FROM %s WHERE siteName=%%s;" % settings["dbConf"]["namesDb"], (settings[self.settingsDictKey]["shortName"], ))
		links = [link[0] for link in cur.fetchall()]
		return links

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

			if totalArt != len(artPages):
				self.log.warning("May be missing art? Total claimed art items from front-page = %s, total gallery items %s", totalArt, len(artPages))
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






			# self._updatePreviouslyRetreived(artist, tmp)

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
			for aName in nameList:
				future_to_url[executor.submit(self.getArtist, aName, ctrlNamespace)] = aName

			for future in concurrent.futures.as_completed(future_to_url):
				# aName = future_to_url[future]
				# res = future.result()
				errored  |= future.result()
				# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

		if errored:
			self.log.warn("Had errors!")

		# ul = plugins.uploaders.eHentai.eHentaiUl.UploadEh()
		# # ul.syncGalleryIds()
		# ul.go(ctrlNamespace=ctrlNamespace, ulFilter=[self.settingsDictKey])

		self.statusMgr.updateRunningStatus(self.settingsDictKey, False)
		runTime = time.time()-startTime
		self.statusMgr.updateLastRunDuration(self.settingsDictKey, runTime)



	@classmethod
	def runScraper(cls, managedNamespace):
		instance = cls()
		instance.go(ctrlNamespace=managedNamespace)

