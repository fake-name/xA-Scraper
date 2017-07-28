
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
		try:
			ret = self._go(*args, **kwargs)
			return (self.out_buffer, ret)
		except Exception as e:
			import sys
			log_txt = '\n	'.join(self.out_buffer)
			exc_message = '{}\nLog report:\n	{}'.format(str(e), log_txt)
			rebuilt = type(e)(exc_message).with_traceback(sys.exc_info()[2])
			rebuilt.log_data = self.out_buffer
			raise rebuilt

	# # ------------------------------------------------------------------------
	# User-facing type things
	# # ------------------------------------------------------------------------

	def yp_walk_to_entry(self):
		gateway = 'https://8ch.net/fur/res/22069.html'
		step1 = self.wg.getpage(gateway)
		self.log.debug("Step 1")
		extraHeaders = {
					"Referer"       : gateway,
		}

		step2 = self.wg.getpage('https://yiff.party/zauth', addlHeaders=extraHeaders)
		self.log.debug("Step 2")

		if 'What is the name of the character pictured above?' in step2:
			self.log.info("Need to step through confirmation page.")
			params = {
				'act'       : 'anon_auth',
				'challenge' : 'anon_auth_1',
				'answer'    : 'nate',
			}
			step3 = self.wg.getpage('https://yiff.party/intermission', postData=params)
			self.log.debug("Step 3")
		else:
			step3 = step2

		if 'You have no favourite creators!' in step3:
			self.log.info("Reached home page!")
			return True
		else:
			self.log.error("Failed to reach home page!")
			self.log.error("Step 1")
			for line in step1.split("\n"):
				self.log.error("	%s", line)
			self.log.error("Step 2")
			for line in step2.split("\n"):
				self.log.error("	%s", line)
			self.log.error("Step 3")
			for line in step3.split("\n"):
				self.log.error("	%s", line)
			return False

	def yp_get_names(self):
		self.log.info("Getting available artist names!")
		ok = self.yp_walk_to_entry()
		if ok:
			return self.wg.getpage('https://yiff.party/creators2.json', addlHeaders={"Referer" : 'https://yiff.party/'})
		else:
			return None

	def get_meta_from_release_soup(self, release_soup):
		retv = {}

		name = release_soup.find('span', class_='yp-info-name')
		if name:
			retv['artist_name'] = name.get_text(strip=True)

		return retv

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
					attachments.append({'url' : url,  'fname' : content})

			# Somehow, some of the files don't show up
			# as attachments. Dunno why.
			action_div = postdiv.find("div", class_='card-action')
			if action_div:
				for link in action_div.find_all("a"):
					url = urllib.parse.urljoin(self.url_base, link['href'])
					content = link.get_text(strip=True)
					attachments.append({'url' : url,  'fname' : content})

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

			file = {}
			file['title'] = list(file_div.find(True, class_='card-title').stripped_strings)[0]
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

		meta = self.get_meta_from_release_soup(soup)

		posts = self.get_posts_from_page(soup)
		files = self.get_files_from_page(soup)

		return {
			'meta'   : meta,
			'posts' : posts,
			'files' : files,
		}

	def fetch_post_content(self, aid, post):

		for attachment in post['attachments']:
			self.log.info("Fetching post file: %s -> %s", aid, attachment['url'])
			filectnt, fname         = self.wg.getFileAndName(attachment['url'], addlHeaders={"Referer" : 'https://yiff.party/{}'.format(aid)})
			self.log.info("Filename from request: %s", fname)
			attachment['header_fn'] = fname
			attachment['fdata']     = filectnt

	def fetch_file_content(self, aid, post):

		for attachment in post['attachments']:
			self.log.info("Fetching attachment file: %s -> %s", aid, attachment['url'])
			filectnt, fname         = self.wg.getFileAndName(attachment['url'], addlHeaders={"Referer" : 'https://yiff.party/{}'.format(aid)})
			self.log.info("Filename from request: %s", fname)
			attachment['header_fn'] = fname
			attachment['fdata']     = filectnt

	def fetch_files(self, aid, releases, have_posts, file_limit):
		self.log.info("Have posts: %s", have_posts)
		fetched = 0
		for post in releases['posts']:
			key = ['post', post['id']]
			if key in have_posts:
				self.log.info("Have post %s, nothing to do", key)
			elif fetched > file_limit:
				self.log.info("Skipping %s due to fetch limit %s.", key, file_limit)
			else:
				self.log.info("Item %s not present in already-fetched items.", key)
				post['files'] = self.fetch_post_content(aid, post)
				fetched += 1


		for file in releases['files']:
			key = ['post', file['title']]
			if key in have_posts:
				self.log.info("Have file %s, nothing to do", key)
			elif fetched > file_limit:
				self.log.info("Skipping %s due to fetch limit %s.", key, file_limit)
			else:
				self.log.info("File %s not present in already-fetched items.", key)
				file['files'] = self.fetch_file_content(aid, file)
				fetched += 1

		return releases


	def yp_get_content_for_artist(self, aid, have_posts, file_limit=100):
		self.log.info("Getting content for artist: %s", aid)
		ok = self.yp_walk_to_entry()
		if not ok:
			return "Error! Failed to access entry!"

		releases = self.get_releases_for_aid(aid)
		releases = self.fetch_files(aid, releases, have_posts, file_limit)
		# else:
		self.log.info("Content retreival finished.")
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
				# self.pprint_resp(ret)
				if 'jobid' in ret and ret['jobid'] == jid:
					if 'ret' in ret:
						if len(ret['ret']) == 2:
							self.print_remote_log(ret['ret'][0])
							return ret['ret'][1]
					else:
						with open('rerr-{}.json'.format(time.time()), 'w', encoding='utf-8') as fp:
							fp.write(json.dumps(ret, indent=4, sort_keys=True))
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
					row = self.db.ScrapeTargets(
							site_name   = self.targetShortName,
							artist_name = name,
							extra_meta  = adict,
							release_cnt = adict['post_count']
							)


					sess.add(row)

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

	def get_save_dir(self, aname):

		dirp = self.getDownloadPath(self.dlBasePath, aname)
		if not os.path.exists(dirp):
			os.makedirs(dirp)
		return dirp

	def save_file(self, aname, filename, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, filename)

		if os.path.exists(fqpath):
			if open(fqpath, "rb").read() == filecontent:
				self.log.info("File exactly matches existing item. Doing an overwrite")
			else:
				cnt = 0
				pathroot, ext = os.path.splitext(fqpath)
				while os.path.exists(fqpath):
					fqpath = "{} - ({}){}".format(pathroot, cnt, ext)
					cnt += 1
					self.log.info("New file with the same name as existing file. Adding number: %s", fqpath)

		with open(fqpath, "wb") as fp:
			fp.write(filecontent)

		return fqpath

	def save_files(self, sess, arow, prow, attachments):
		have_all = True
		for file in attachments:
			if 'fdata' in file:
				urlname = urllib.parse.urlsplit(file['url']).path
				urlfn = os.path.split(urlname)[-1]
				resname = "{} {}".format(file['header_fn'], urlfn).strip()

				aname = "{} - {}".format(arow.id, arow.extra_meta['name'])
				fqDlPath = self.save_file(aname, resname, file['fdata'])
				self.log.info("Saving file to '%s'", fqDlPath)

				frow = sess.query(self.db.ArtFile) \
					.filter(self.db.ArtFile.item_id == prow.id) \
					.filter(self.db.ArtFile.file_meta == resname) \
					.scalar()

				if frow:
					if frow.fspath != fqDlPath:
						self.log.error("Item already exists, but download path is changing?")
						self.log.error("Old path: '%s'", frow.fspath)
						self.log.error("New path: '%s'", fqDlPath)
						frow.fspath = fqDlPath
				else:
					frow = self.db.ArtFile(
							item_id   = prow.id,
							file_meta = resname,
							filename  = resname,
							fspath    = fqDlPath,
						)
					sess.add(frow)
				sess.commit()

			else:
				have_all = False

		return 'complete' if have_all else 'error'

	def _process_response_post(self, arow, post_struct):
		with self.db.context_sess() as sess:
			have = sess.query(self.db.ArtItem)                             \
				.filter(self.db.ArtItem.artist_id    == arow.id)           \
				.filter(self.db.ArtItem.release_meta == post_struct['id']) \
				.scalar()
			if have:
				self.log.info("Have post: '%s'", post_struct['title'])
				if post_struct['attachments']:
					result = self.save_files(sess, arow, have, post_struct['attachments'])
					self.log.info("Saved attachment result: %s", result)
					have.state = result
				else:
					have.state = 'complete'
					self.log.info("Post '%s' has no attachments?", post_struct['title'])


			else:
				self.log.info("New post: '%s'", post_struct['title'])
				post_struct['type'] = 'post'
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
				sess.flush()

				if post_struct['attachments']:
					result = self.save_files(sess, arow, have, post_struct['attachments'])
					self.log.info("Saved attachment result: %s", result)
					have.state = result
				else:
					have.state = 'complete'
					self.log.info("Post '%s' has no attachments?", post_struct['title'])





	def _process_response_file(self, arow, post_struct):
		with self.db.context_sess() as sess:
			have = sess.query(self.db.ArtItem)                             \
				.filter(self.db.ArtItem.artist_id    == arow.id)           \
				.filter(self.db.ArtItem.release_meta == post_struct['title']) \
				.scalar()
			if have:
				self.log.info("Have attachment: '%s'", post_struct['title'])
				if post_struct['attachments']:
					result = self.save_files(sess, arow, have, post_struct['attachments'])
					self.log.info("Saved file result: %s", result)
					have.state = result
				if not post_struct['attachments']:
					self.log.info("File post '%s' is missing the actual file?", post_struct['title'])
					have.state = 'complete'

			else:
				self.log.info("New attachment: '%s'", post_struct['title'])
				post_struct['type'] = 'file'
				have = self.db.ArtItem(
						state              = 'new',
						artist_id          = arow.id,
						release_meta       = post_struct['title'],
						addtime            = datetime.datetime.fromtimestamp(float(post_struct['post_ts'])),
						title              = post_struct['title'],
						content_structured = post_struct,
					)

				if post_struct['attachments']:
					result = self.save_files(sess, arow, have, post_struct['attachments'])
					self.log.info("Saved file result: %s", result)
					have.state = result
				if not post_struct['attachments']:
					self.log.info("File post '%s' is missing the actual file?", post_struct['title'])
					have.state = 'complete'

				sess.add(have)


	def do_fetch_by_aid(self, aid):

		with self.db.context_sess() as sess:
			arow = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == aid).one()

		print(arow, arow.id, arow.site_name, arow.artist_name, arow.extra_meta)
		have = [
					(post.content_structured['type'], post.content_structured['id'] if 'id' in post.content_structured else post.content_structured['title'])
				for
					post in arow.posts
				if
					post.state != 'new'
			]
		print()
		print(have)
		print()
		for item in have:
			print(item)

		print()
		print()


		resp = self.blocking_remote_call(RemoteExecClass, {'mode' : 'get-art-for-aid', 'aid' : arow.artist_name, 'have_posts' : have })
		# resp = self.blocking_remote_call(RemoteExecClass, {'mode' : 'get-art-for-aid', 'aid' : arow.artist_name })

		with open('rfetch-{}.json'.format(time.time()), 'w', encoding='utf-8') as fp:
			fp.write(pprint.pformat(resp))

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

	if True:
		ins = GetYp()
		# ins.getCookie()
		print(ins)
		print("Instance: ", ins)
		# ins.go("Wat", "Wat")
		# ret = ins.do_fetch_by_aid(3745)
		ret = ins.do_fetch_by_aid(5688)
		print(ret)
		# ins.do_fetch_by_aid(8450)   # z
		# dlPathBase, artPageUrl, artistName
	else:
		local_test()



