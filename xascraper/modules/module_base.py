
import os
import os.path
import logging
from settings import settings
from WebRequest import WebGetRobust
import threading
import abc

import xascraper.status_monitor
import xascraper.database
import xascraper.status_monitor

class ModuleBase(xascraper.status_monitor.StatusMixin, metaclass=abc.ABCMeta):

	# Abstract class (must be subclassed)
	__metaclass__ = abc.ABCMeta

	db = xascraper.database

	@abc.abstractmethod
	def pluginName(self):
		return None

	custom_ua = None

	def __init__(self):
		print("Starting up")
		self.loggers = {}
		self.lastLoggerIndex = 1


		self.log = logging.getLogger("Main.%s" % self.pluginName)
		self.wg = WebGetRobust(
			custom_ua           = self.custom_ua,
			twocaptcha_api_key  = settings.get("captcha", {}).get('2captcha', {})    .get("api_key", None),
			anticaptcha_api_key = settings.get("captcha", {}).get('anti-captcha', {}).get("api_key", None),
			)

		print("Starting up?")

		super().__init__()


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

		else:
			return object.__getattribute__(self, name)


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# FS Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getDownloadPath(self, siteSource, artist):
		return os.path.join(settings["dldCtntPath"], siteSource, artist)

	def _checkFileExists(self, filePath):
		# Return true if file exists
		# false if it does not
		# eventually will allow overwriting on command

		if os.path.exists(filePath):
			if os.path.getsize(filePath) > 100:
				return True
		return False

