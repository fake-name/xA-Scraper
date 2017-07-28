
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

from . import yiff_remote

class RpcTimeoutError(RuntimeError):
	pass
class RpcExceptionError(RuntimeError):
	pass



class GetYp(rewrite.modules.scraper_base.ScraperBase, rewrite.modules.rpc_base.RpcMixin):


	settingsDictKey = "yp"

	pluginName = "YpGet"

	rpc_timeout_s = 60 * 15

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
		if len(resp) == 2:
			logmsg, response_data = resp
			self.print_remote_log(logmsg)
		for line in pprint.pformat(resp).split("\n"):
			self.log.info(line)
		if 'traceback' in resp:
			for line in resp['traceback'].split("\n"):
				self.log.error(line)

	def print_remote_log(self, log_lines, debug=False):
		calls = {
				"[DEBUG] ->"    : self.remote_log.debug if debug else None,
				"[INFO] ->"     : self.remote_log.info,
				"[ERROR] ->"    : self.remote_log.error,
				"[CRITICAL] ->" : self.remote_log.critical,
				"[WARNING] ->"  : self.remote_log.warning,
			}

		for line in log_lines:
			for key, log_call in calls.items():
				if key in line and log_call:
					log_call(line)


	def blocking_remote_call(self, remote_cls, call_kwargs):
		jid = str(uuid.uuid4())

		scls = self.serialize_class(remote_cls)
		self.put_outbound_callable(jid, scls, call_kwargs=call_kwargs)

		self.log.info("Waiting for remote response")
		for _ in range(self.rpc_timeout_s):
			ret = self.process_responses()
			if ret:
				if 'jobid' in ret and ret['jobid'] == jid:
					if 'ret' in ret:
						if len(ret['ret']) == 2:
							self.print_remote_log(ret['ret'][0])
							return ret['ret'][1]
						else:
							self.pprint_resp(ret)
							raise RuntimeError("Response not of length 2!")
					else:
						with open('rerr-{}.json'.format(time.time()), 'w', encoding='utf-8') as fp:
							fp.write(json.dumps(ret, indent=4, sort_keys=True))
						self.pprint_resp(ret)
						raise RpcExceptionError("RPC Call has no ret value. Probably encountered a remote exception: %s" % ret)

			time.sleep(1)

		raise RpcTimeoutError("No RPC Response within timeout period (%s sec)" % self.rpc_timeout_s)


	def fetch_update_names(self):
		name_json = self.blocking_remote_call(yiff_remote.RemoteExecClass, {'mode' : 'yp_get_names'})
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
				print("File missing 'fdata': %s", file)
				have_all = False

		ret = 'complete' if have_all else 'error'
		self.log.info("Save files state: %s", ret)
		return ret

	def _process_response_post(self, sess, arow, post_struct):
		have = sess.query(self.db.ArtItem)                             \
			.filter(self.db.ArtItem.artist_id    == arow.id)           \
			.filter(self.db.ArtItem.release_meta == post_struct['id']) \
			.scalar()
		if have:
			self.log.info("Have post: '%s'", post_struct['title'])
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
					content_structured = {i:post_struct[i] for i in post_struct if i!='attachments'},
				)
			sess.add(have)
			sess.flush()

		if post_struct['attachments']:
			if 'skipped' in post_struct and post_struct['skipped'] == True:
				self.log.info("Attachment skipped due to fetch limit.")
				have.state = "new"
			else:
				result = self.save_files(sess, arow, have, post_struct['attachments'])
				self.log.info("Saved attachment result: %s", result)
				have.state = result
		else:
			have.state = 'complete'
			self.log.info("Post '%s' has no attachments?", post_struct['title'])

		sess.commit()


	def _process_response_file(self, sess, arow, post_struct):

		have = sess.query(self.db.ArtItem)                             \
			.filter(self.db.ArtItem.artist_id    == arow.id)           \
			.filter(self.db.ArtItem.release_meta == post_struct['title']) \
			.scalar()

		if have:
			self.log.info("Have attachment: '%s'", post_struct['title'])
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
			sess.add(have)
			sess.flush()

		print("File struct: ", post_struct)

		if 'skipped' in post_struct and post_struct['skipped'] == True:
			self.log.info("File skipped due to fetch limit.")
			have.state = "new"
		else:
			result = self.save_files(sess, arow, have, post_struct['attachments'])
			self.log.info("Saved file result: %s", result)
			have.state = result
		if not post_struct['attachments']:
			self.log.info("File post '%s' is missing the actual file?", post_struct['title'])
			have.state = 'complete'

		sess.commit()

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
					and
						(
							(
								post.files
							and
								all([os.path.exists(file.fspath) for file in post.files])
							)
							or not post.files
						)


			]

		nofile = [
					post
				for
					post in arow.posts
				if
						post.state != 'new'
					and not post.files
					# and
					# 	all([os.path.exists(file.fspath) for file in post.files])
			]
		print()
		print(have)
		print()
		for item in have:
			print("have", item)

		print()
		for item in nofile:
			print(item, len(item.files), item.title, item.release_meta)

		print()

		assert len(have) > 15


		resp = self.blocking_remote_call(RemoteExecClass, {'mode' : 'yp_get_content_for_artist', 'aid' : arow.artist_name, 'have_posts' : have, 'file_limit' : 10})
		# resp = self.blocking_remote_call(RemoteExecClass, {'mode' : 'yp_get_content_for_artist', 'aid' : arow.artist_name })

		with open('rfetch-{}.json'.format(time.time()), 'w', encoding='utf-8') as fp:
			fp.write(pprint.pformat(resp))

		if resp['meta']['artist_name'].lower() != arow.extra_meta['name'].lower():
			self.log.error("Artist name mismatch! '%s' -> '%s'", resp['meta']['artist_name'], arow.extra_meta['name'])
			return
		with self.db.context_sess() as sess:
			for post in resp['posts']:
				self._process_response_post(sess, arow, post)
			for file in resp['files']:
				self._process_response_file(sess, arow, file)

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



