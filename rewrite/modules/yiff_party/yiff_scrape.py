
import os
import os.path
import traceback
import re
import logging
import datetime
import urllib.request
import urllib.parse
import time
import json
import uuid
import pprint

import bs4
import dateparser

import rewrite.modules.scraper_base
import rewrite.modules.rpc_base

import flags

from settings import settings

class RpcTimeoutError(RuntimeError):
	pass
class RpcExceptionError(RuntimeError):
	pass


class RemoteExecClass(object):
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Runtime management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	url_base = 'https://yiff.party/'

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

	def get_meta_from_release_soup(self, release_soup):
		ret = {}

		name = release_soup.find('span', class_='yp-info-name')
		if name:
			ret['artist_name'] = name.get_text(strip=True)

		return ret

	def get_posts_from_page(self, soup):
		posts = []
		postdivs = soup.find_all("div", class_='yp-post')
		for postdiv in postdivs:
			post = {}
			post['id'] = postdiv['id']

			post['time']  = postdiv.find(True, class_='post-time' ).get_text(strip=True)
			post['title'] = list(postdiv.find("span", class_='card-title').stripped_strings)[0]
			post['body']  = postdiv.find("div",   class_='post-body' ).get_text(strip=True)

			attachment_div = postdiv.find("div", class_='card-attachments')
			attachments = []
			if attachment_div:
				for link in attachment_div.find_all("a"):
					url = urllib.parse.urljoin(self.url_base, link['href'])
					content = link.get_text(strip=True)
					attachments.append((url, content))
			post['attachments'] = attachments

			comments = []
			for comment_div in postdiv.find_all('div', class_='yp-post-comment'):
				comment = {}
				comment['content']  = comment_div.find(True, class_='yp-post-comment-body').get_text(strip=True)
				comment['time_utc'] = comment_div.find(True, class_='yp-post-comment-time')['data-utc']
				comment['author']   = list(comment_div.find(True, class_='yp-post-comment-head').stripped_strings)[0]

				comments.append(comment)
			post['comments'] = comments
			posts.append(post)

		return posts

	def get_files_from_page(self, soup):
		files = []
		file_divs = soup.find_all('div', class_='yp-shared-card')
		for file_div in file_divs:

			print('content')
			print(file_div.prettify())

			file = {}
			file['title'] = file_div.find(True, class_='card-title').get_text(strip=True)
			file['post_ts'] = file_div.find(True, class_='post-time-unix').get_text(strip=True)

			content = file_div.find('div', class_='card-action')

			file['attachments'] = [
				(tmp.get_text(strip=True), urllib.parse.urljoin(self.url_base, tmp['href'])) for tmp in content.find_all('a')
			]
			files.append(file)

		return files


	def get_releases_for_aid(self, aid):
		soup = self.wg.getSoup('https://yiff.party/{}'.format(aid), addlHeaders={"Referer" : 'https://yiff.party/'})

		# Clear out the material design icons.
		for baddiv in soup.find_all("i", class_='material-icons'):
			baddiv.decompose()

		ret = self.get_meta_from_release_soup(soup)

		posts = self.get_posts_from_page(soup)
		files = self.get_files_from_page(soup)

		return {
			'meta'   : meta,
			'posts' : posts,
			'files' : files,
		}

	def yp_get_content_for_artist(self, aid):
		self.log.info("Getting content for artist: %s", aid)
		ok = self.yp_walk_to_entry()
		if not ok:
			return "Error! Failed to access entry!"

		releases = self.get_releases_for_aid(aid)

		# else:
		return releases

	def _go(self, mode, **kwargs):
		self.log.info("_go() called with mode: '%s'", mode)
		self.log.info("_go() kwargs: '%s'", kwargs)

		if mode == 'get-names':
			return self.yp_get_names()
		elif mode == "get-art-for-aid":
			return self.yp_get_content_for_artist(**kwargs)
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
			if ret:

				self.pprint_resp(ret)
				if 'jobid' in ret and ret['jobid'] == jid:
					if 'ret' in ret:
						if len(ret['ret']) == 2:
							self.print_remote_log(ret['ret'][0])
							return ret['ret'][1]
					else:
						raise RpcExceptionError("RPC Call has no ret value. Probably encountered a remote exception: %s" % ret)

			time.sleep(1)

		raise RpcTimeoutError("No RPC Response within timeout period (%s sec)" % self.rpc_timeout_s)


	def fetch_update_names(self):
		name_json = self.blocking_remote_call(RemoteExecClass, {'mode' : 'get-names'})
		namelist = json.loads(name_json)
		new     = 0
		updated = 0

		# Push the name list into the DB
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
		self.fetch_update_names()
		return super().getNameList()


	def _process_response_post(self, arow, post_struct):
		with self.db.context_sess() as sess:
			have = sess.query(self.db.ArtItem)                             \
				.filter(self.db.ArtItem.artist_id    == arow.id)           \
				.filter(self.db.ArtItem.release_meta == post_struct['id']) \
				.scalar()
			if not have:
				have = self.db.ArtItem(
						state              = 'new',
						artist_id          = arow.id,
						release_meta       = post_struct['id'],
						addtime            = dateparser.parse(post_struct['time']),
						title              = post_struct['title'],
						content            = post_struct['body'],
						content_structured = post_struct,
					)
				sess.add(have)


	def _process_response_file(self, arow, post_struct):
		with self.db.context_sess() as sess:
			have = sess.query(self.db.ArtItem)                             \
				.filter(self.db.ArtItem.artist_id    == arow.id)           \
				.filter(self.db.ArtItem.release_meta == post_struct['title']) \
				.scalar()
			if not have:
				have = self.db.ArtItem(
						state              = 'new',
						artist_id          = arow.id,
						release_meta       = post_struct['title'],
						addtime            = datetime.datetime.fromtimestamp(post_struct['post_ts']),
						title              = post_struct['title'],
					)
				sess.add(have)


	def do_fetch_by_aid(self, aid):

		with self.db.context_sess() as sess:
			arow = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == aid).one()

		print(arow, arow.id, arow.site_name, arow.artist_name, arow.extra_meta)

		resp = self.blocking_remote_call(RemoteExecClass, {'mode' : 'get-art-for-aid', 'aid' : arow.artist_name})

		with open('rfetch.txt', 'w', encoding='utf-8') as fp:
			fp.write(json.dumps(resp))

		if resp['meta']['artist_name'].lower() != arow.extra_meta['name'].lower():
			self.log.error("Artist name mismatch! '%s' -> '%s'", resp['meta']['artist_name'], arow.extra_meta['name'])
			return

		for post in resp['posts']:
			self._process_response_post(arow, post)
		for file in resp['files']:
			self._process_response_file(arow, file)

		with self.db.context_sess() as sess:
			arow.last_fetched = datetime.datetime.now()

	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")

		nl = self.getNameList()

		for aid, _ in nl:
			self.do_fetch_by_aid(aid)


def local_test():
	import webFunctions
	import bs4
	import sys
	wg = webFunctions.WebGetRobust()
	t2 = RemoteExecClass(wg=wg)
	with open(sys.argv[1], "r") as fp:
		cont=fp.read()
	soup = bs4.BeautifulSoup(cont, 'lxml')

	r1 = t2.get_meta_from_release_soup(soup)
	r2 = t2.get_posts_from_page(soup)
	r3 = t2.get_files_from_page(soup)

	pprint.pprint(("R1:", r1))
	pprint.pprint(("R2:", r2))
	pprint.pprint(("R2:", r3))

if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	if False:
		ins = GetYp()
		# ins.getCookie()
		print(ins)
		print("Instance: ", ins)
		# ins.go("Wat", "Wat")
		ret = ins.do_fetch_by_aid(3745)
		# ret = ins.do_fetch_by_aid(5688)
		print(ret)
		# ins.do_fetch_by_aid(8450)   # z
		# dlPathBase, artPageUrl, artistName
	else:
		local_test()



