
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
import uuid
import pprint

import rewrite.modules.scraper_base
import rewrite.modules.rpc_base


import logging

class RpcTimeoutError(RuntimeError):
	pass


class RemoteExecClass(object):
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Runtime management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, wg=None):
		self.logname = "Main.RemoteExec.Tester"
		self.out_buffer = []

		self.wg = wg

		self.__install_logproxy()

		self.log.info("RemoteExecClass Instantiated")

	def __install_logproxy(self):
		class LogProxy():
			def __init__(self, parent_logger, log_prefix):
				self.parent_logger = parent_logger
				self.log_prefix    = log_prefix
			def debug(self, msg, *args):
				self.parent_logger._debug   (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def info(self, msg, *args):
				self.parent_logger._info    (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def error(self, msg, *args):
				self.parent_logger._error   (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def critical(self, msg, *args):
				self.parent_logger._critical(" [{}] -> ".format(self.log_prefix) + msg, *args)
			def warning(self, msg, *args):
				self.parent_logger._warning (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def warn(self, msg, *args):
				self.parent_logger._warning (" [{}] -> ".format(self.log_prefix) + msg, *args)

		self.wg.log = LogProxy(self, "WebGet")
		self.log    = LogProxy(self, "MainRPCAgent")


	def _debug(self, msg, *args):
		tmp = self.logname + " [DEBUG] ->" + msg % args
		self.out_buffer.append(tmp)
	def _info(self, msg, *args):
		tmp = self.logname + " [INFO] ->" + msg % args
		self.out_buffer.append(tmp)
	def _error(self, msg, *args):
		tmp = self.logname + " [ERROR] ->" + msg % args
		self.out_buffer.append(tmp)
	def _critical(self, msg, *args):
		tmp = self.logname + " [CRITICAL] ->" + msg % args
		self.out_buffer.append(tmp)
	def _warning(self, msg, *args):
		tmp = self.logname + " [WARNING] ->" + msg % args
		self.out_buffer.append(tmp)



	def go(self, *args, **kwargs):
		return (self.out_buffer, self._go(*args, **kwargs))

	# # ------------------------------------------------------------------------
	# User-facing type things
	# # ------------------------------------------------------------------------

	def yp_walk_to_entry(self):
		gateway = 'https://8ch.net/fur/res/22069.html'
		step1 = self.wg.getpage(gateway)
		self.log.debug("Step 1: '%s'", step1)
		extraHeaders = {
					"Referer"       : gateway,
		}

		step2 = self.wg.getpage('https://yiff.party/zauth', addlHeaders=extraHeaders)
		self.log.debug("Step 2: '%s'", step2)

		if 'What is the name of the character pictured above?' in step2:
			self.log.info("Need to step through confirmation page.")
			params = {
				'act'       : 'anon_auth',
				'challenge' : 'anon_auth_1',
				'answer'    : 'nate',
			}
			step3 = self.wg.getpage('https://yiff.party/intermission', postData=params)
			self.log.debug("Step 3: '%s'", step3)
		else:
			step3 = step2

		if 'You have no favourite creators!' in step3:
			self.log.info("Reached home page!")
			return True
		else:
			self.log.error("Failed to reach home page!")
			return False

	def yp_get_names(self):
		self.log.info("Getting available artist names!")
		ok = self.yp_walk_to_entry()
		if ok:
			return self.wg.getpage('https://yiff.party/creators2.json', addlHeaders={"Referer" : 'https://yiff.party/'})
		else:
			return None

	def _go(self, mode, **kwargs):
		self.log.info("_go() called with mode: '%s'", mode)
		self.log.info("_go() kwargs: '%s'", kwargs)

		if mode == 'get-names':
			return self.yp_get_names()
		else:
			self.log.error("Unknown mode: '%s'", mode)
			return "Unknown mode: '%s' -> Kwargs: '%s'" % (mode, kwargs)




class GetYp(rewrite.modules.scraper_base.ScraperBase, rewrite.modules.rpc_base.RpcMixin):


	settingsDictKey = "yp"

	pluginName = "YpGet"

	rpc_timeout_s = 600

	remote_log = logging.getLogger("Main.RPC.Remote")

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

	def pprint_resp(self, resp):
		for line in pprint.pformat(resp).split("\n"):
			self.log.info(line)
		if 'traceback' in resp:
			for line in resp['traceback'].split("\n"):
				self.log.error(line)

	def print_remote_log(self, log_lines):
		calls = {
				"[DEBUG] ->"    : self.remote_log.debug,
				"[INFO] ->"     : self.remote_log.info,
				"[ERROR] ->"    : self.remote_log.error,
				"[CRITICAL] ->" : self.remote_log.critical,
				"[WARNING] ->"  : self.remote_log.warning,
			}

		for line in log_lines:
			for key, log_call in calls.items():
				if key in line:
					log_call(line)


	def blocking_remote_call(self, remote_cls, call_kwargs):
		jid = str(uuid.uuid4())

		scls = self.serialize_class(remote_cls)
		self.put_outbound_callable(jid, scls, call_kwargs=call_kwargs)

		self.log.info("Waiting for remote response")
		for _ in range(self.rpc_timeout_s):
			ret = self.process_responses()
			# print(ret, _)
			if ret:
				# self.pprint_resp(ret)
				if 'jobid' in ret and ret['jobid'] == jid:
					if len(ret['ret']) == 2:
						self.print_remote_log(ret['ret'][0])
						return ret['ret'][1]
			time.sleep(1)


		raise RpcTimeoutError("No RPC Response within timeout period (%s sec)" % self.rpc_timeout_s)


	def fetch_update_names(self):
		name_json = self.blocking_remote_call(RemoteExecClass, {'mode' : 'get-names'})
		namelist = json.loads(name_json)
		new     = 0
		updated = 0
		# Push the pixiv name list into the DB
		with self.db.context_sess() as sess:
			for adict in namelist['creators']:
				name = str(adict['id'])
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()

				if not res:
					new += 1
					self.log.info("Need to insert name: %s", name)
					sess.add(
						self.db.ScrapeTargets(
							site_name   = self.targetShortName,
							artist_name = name,
							extra_meta  = adict,
							release_cnt = adict['post_count']
							)
						)
					sess.commit()

				elif res.extra_meta != adict:
					res.extra_meta   = adict
					res.last_fetched = datetime.datetime.min
					sess.commit()
					updated += 1

		self.log.info("Had %s new names, %s with changes since last update.", new, updated)

	def getNameList(self):

		# self.fetch_update_names()
		return super().getNameList()


	def do_fetch_by_aid(self, aid):

		with self.db.context_sess() as sess:
			row = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == aid).one()
		print(row, row.id, row.site_name, row.artist_name, row.extra_meta)


	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")


		nl = self.getNameList()

		for aid, _ in nl:
			self.do_fetch_by_aid(aid)



if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	ins = GetYp()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)
	ins.go("Wat", "Wat")
	# dlPathBase, artPageUrl, artistName




