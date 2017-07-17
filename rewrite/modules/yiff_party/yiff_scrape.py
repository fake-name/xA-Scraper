
import os
import os.path
import traceback
import re
import bs4
import dateparser
import datetime
import urllib.request
import urllib.parse
from settings import settings
import flags
import time
import json

import rewrite.modules.scraper_base
import rewrite.modules.rpc_base


import logging


class TestClass(object):
	def __init__(self, wg=None):
		self.log = logging.getLogger("Main.RemoteExec.Tester")
		self.wg = wg
		self.log.info("TestClass Instantiated")

	def test_internal(self):
		ret = 'wut'
		ret += "\n" + str(self.wg)
		ret += "\n" + str(self.log)

		ret += "\n" + str(dill)
		ret += "\n" + str(logging)
		ret += "\n" + str(urllib.parse)
		ret += "\n" + str(socket)
		ret += "\n" + str(traceback)
		ret += "\n" + str(threading)
		ret += "\n" + str(multiprocessing)
		ret += "\n" + str(queue)
		ret += "\n" + str(time)
		ret += "\n" + str(json)
		ret += "\n" + str(mimetypes)
		ret += "\n" + str(re)
		ret += "\n" + str(bs4)
		ret += "\n" + str(urllib.request)
		ret += "\n" + str(urllib.parse)
		ret += "\n"
		ret += "\n" + str(locals())
		ret += "\n" + str(globals())

		ret += "\n"
		ret += "\n" + self.wg.getpage("http://example.org/")
		return ret



	def go(self):
		self.log.info("TestClass go() called")
		self.log.info("WG: %s", self.wg)

		return ("Test sez wut?", self.test_internal())



class GetYp(rewrite.modules.scraper_base.ScraperBase, rewrite.modules.rpc_base.RpcMixin):


	settingsDictKey = "yp"

	pluginName = "YpGet"


	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Giant bunch of stubs to shut up the abstract base class
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getArtPage(self):
		pass
	def _getGalleries(self):
		pass
	def _getItemsOnPage(self):
		pass
	def _getTotalArtCount(self):
		pass
	def checkCookie(self):
		return
	def getCookie(self):
		return

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # We completely override the normal exec behaviour
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")

		# ret = self.put_outbound_fetch_job(123456, 'https://stackoverflow.com/questions/33738467/how-do-i-know-if-i-can-disable-sqlalchemy-track-modifications')

		scls = self.serialize_class(TestClass)

		ret2 = self.put_outbound_callable(123457, scls)

		# print(ret)
		print(ret2)
		for _ in range(360):
			ret = self.process_responses()
			print(ret, _)
			time.sleep(1)

		# self.updateRunningStatus(self.settingsDictKey, True)
		# startTime = datetime.datetime.now()
		# self.updateLastRunStartTime(self.settingsDictKey, startTime)

		# if not nameList:
		# 	nameList = self.getNameList()

		# haveCookie, dummy_message = self.checkCookie()
		# if not haveCookie:
		# 	self.log.info("Do not have login cookie. Retreiving one now.")
		# 	cookieStatus = self.getCookie()
		# 	self.log.info("Login attempt status = %s.", cookieStatus)

		# haveCookie, dummy_message = self.checkCookie()
		# if not haveCookie:
		# 	self.log.critical("Failed to download cookie! Exiting!")
		# 	return False


		# errored = False

		# # Farm out requests to the thread-pool
		# with concurrent.futures.ThreadPoolExecutor(max_workers=self.numThreads) as executor:

		# 	future_to_url = {}
		# 	for aId, aName in nameList:
		# 		future_to_url[executor.submit(self.getArtist, aName, ctrlNamespace)] = aName

		# 	for future in concurrent.futures.as_completed(future_to_url):
		# 		# aName = future_to_url[future]
		# 		# res = future.result()
		# 		errored  |= future.result()
		# 		# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

		# if errored:
		# 	self.log.warn("Had errors!")

		# self.updateRunningStatus(self.settingsDictKey, False)
		# runTime = datetime.datetime.now()-startTime
		# self.updateLastRunDuration(self.settingsDictKey, runTime)





if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	ins = GetYp()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)
	ins.go("Wat", "Wat")
	# dlPathBase, artPageUrl, artistName




