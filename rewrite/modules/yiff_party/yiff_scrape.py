
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
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Runtime management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, wg=None):
		self.logname = "Main.RemoteExec.Tester"
		self.out_buffer = []

		self.wg = wg
		self.log_info("TestClass Instantiated")

	def log_debug(self, msg, *args):
		tmp = self.logname + " [DEBUG] ->" + msg % args
		self.out_buffer.append(tmp)
	def log_info(self, msg, *args):
		tmp = self.logname + " [INFO] ->" + msg % args
		self.out_buffer.append(tmp)
	def log_error(self, msg, *args):
		tmp = self.logname + " [ERROR] ->" + msg % args
		self.out_buffer.append(tmp)

	def go(self, *args, **kwargs):
		return (self.out_buffer, self._go(*args, **kwargs))

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# User-facing type things
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def yp_walk_to_entry(self):
		gateway = 'https://8ch.net/fur/res/22069.html'
		step1 = self.wg.getpage(gateway)
		self.log_debug("Step 1: '%s'", step1)
		extraHeaders = {
					"Referer"       : gateway,
		}

		step2 = self.wg.getpage('https://yiff.party/zauth', addlHeaders=extraHeaders)
		self.log_debug("Step 2: '%s'", step2)

		if 'What is the name of the character pictured above?' in step2:
			self.log_info("Need to step through confirmation page.")
			params = {
				'act'       : 'anon_auth',
				'challenge' : 'anon_auth_1',
				'answer'    : 'nate',
			}
			step3 = self.wg.getpage('https://yiff.party/intermission', postData=params)
			self.log_debug("Step 3: '%s'", step3)
		else:
			step3 = step2

		if 'You have no favourite creators!' in step3:
			self.log_info("Reached home page!")
			return True
		else:
			self.log_error("Failed to reach home page!")
			return False

	def yp_get_names(self):
		ok = self.yp_walk_to_entry()
		if ok:
			return self.wg.getpage('https://yiff.party/creators2.json', addlHeaders={"Referer" : 'https://yiff.party/'})
		else:
			return None

	def _go(self, mode, **kwargs):
		if mode == 'get-names:':
			return self.yp_get_names()
		else:
			return (self.out_buffer, self._go())




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




