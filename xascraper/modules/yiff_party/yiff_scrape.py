
import os
import os.path
import traceback
import random
import re
import logging
import datetime
import urllib.request
import urllib.parse
import time
import signal
import json
import sys
import uuid
import pprint
import sqlalchemy.exc

import bs4
import dateparser

import xascraper.modules.scraper_base
import xascraper.modules.rpc_base

import flags

from settings import settings

from . import yiff_remote
from . import local_exec

class RpcTimeoutError(RuntimeError):
	pass
class RpcExceptionError(RuntimeError):
	pass

def batch(iterable, n=1):
	l = len(iterable)
	for ndx in range(0, l, n):
		yield iterable[ndx:min(ndx + n, l)]

PARALLEL_JOBS = 20

class GetYP(xascraper.modules.scraper_base.ScraperBase, xascraper.modules.rpc_base.RpcMixin):


	settingsDictKey = "yp"

	pluginName = "YpGet"

	rpc_timeout_s = 60 * 60 * 24 * 3

	remote_log = logging.getLogger("Main.RPC.Remote")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.job_map = {}

		self.job_counter = 0

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
			if isinstance(resp['traceback'], str):
				trace_arr = resp['traceback'].split("\n")
			else:
				trace_arr = resp['traceback']

			for line in trace_arr:
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

	def put_job(self, remote_cls, call_kwargs=None, meta=None, early_ack=False):

		if call_kwargs is None:
			call_kwargs = {}

		if not meta:
			meta = {}

		jid = str(uuid.uuid4())

		if 'drain' in sys.argv:
			print("Consuming replies only")
			self.check_open_rpc_interface()
		else:
			scls = self.serialize_class(remote_cls)
			# print("Putting job:", jid, call_kwargs)
			self.put_outbound_callable(jid, scls, call_kwargs=call_kwargs, meta=meta, early_ack=early_ack)

		return jid

	def __mark_id_complete(self, jobid):

		if jobid in self.job_map:
			for x in range(50):
				try:
					with self.db.context_sess() as sess:
						arow = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == self.job_map[jobid]).one()
						self.log.info("Marking artist %s as fetched (id: %s)", arow.extra_meta['name'], arow.id)
						arow.last_fetched = datetime.datetime.now()
						sess.commit()
					return

				except sqlalchemy.exc.InvalidRequestError:
					print("InvalidRequest error!")
					sess.rollback()
					if x > 10:
						traceback.print_exc()
						raise
				except sqlalchemy.exc.OperationalError:
					print("Operational error!")
					sess.rollback()
					if x > 10:
						traceback.print_exc()
						raise
				except sqlalchemy.exc.IntegrityError:
					print("Integrity error!")
					sess.rollback()
					if x > 10:
						traceback.print_exc()
						raise
		else:
			self.log.warning("Job id %s not in job_map. Do not know how to cross-correlate to mark complete response",
				jobid)

	def process_response_items(self, jobids, expect_partials, preload_rets = []):
		self.log.info("Waiting for remote response (preloaded: %s)", len(preload_rets))
		timeout = self.rpc_timeout_s * 12

		assert isinstance(jobids, list)

		while timeout or preload_rets:
			timeout -= 1
			if preload_rets:
				self.log.info("Have preloaded item. Using.")
				ret = preload_rets.pop(0)
			else:
				ret = self.process_responses()
			if ret:

				if ('jobid' in ret and ret['jobid'] in jobids) or expect_partials:
					if 'ret' in ret:
						if len(ret['ret']) == 2:
							self.print_remote_log(ret['ret'][0])

							if expect_partials:
								self.log.info("Incremental return because expect_partials is %s", expect_partials)
								if 'partial' in ret and ret['partial']:
									timeout = self.rpc_timeout_s
									yield ret['ret'][1]
								else:
									yield ret['ret'][1]
									if 'jobid' in ret and ret['jobid'] in jobids:

										self.__mark_id_complete(ret['jobid'])

										jobids.remove(ret['jobid'])

										self.log.info("Last partial received for job %s, %s remaining.",
											ret['jobid'], len(jobids))

										if len(jobids) == 0:
											raise StopIteration
									else:
										if 'jobid' in ret:
											self.log.info("Received completed job response from a previous session?")
										else:
											self.log.error("Response that's not partial, and yet has no jobid?")

							else:
								self.log.info("Non incremental return")
								yield ret['ret'][1]
								raise StopIteration
						else:
							self.pprint_resp(ret)
							raise RuntimeError("Response not of length 2!")
					else:
						with open('rerr-{}.json'.format(time.time()), 'w', encoding='utf-8') as fp:
							fp.write(json.dumps(ret, indent=4, sort_keys=True))
						self.pprint_resp(ret)
						raise RpcExceptionError("RPC Call has no ret value. Probably encountered a remote exception: %s" % ret)

			time.sleep(1)
			print("\r`fetch_and_flush` sleeping for {}\r".format(str((timeout)).rjust(7)), end='', flush=True)

		raise RpcTimeoutError("No RPC Response within timeout period (%s sec)" % self.rpc_timeout_s)

	def __blocking_dispatch_call_local(self, remote_cls, call_kwargs, meta=None, expect_partials=False):
		self.log.info("Dispatching new callable job to local executor")

		print("Kwargs:", call_kwargs)
		call_kwargs_out = {}
		# call_kwargs_out = {'code_struct' : serialized}
		for key, value in call_kwargs.items():
			call_kwargs_out[key] = value
		# job = {
		# 		'call'                 : 'callCode',
		# 		'module'               : 'RemoteExec',
		# 		'args'                 : (),
		# 		'kwargs'               : call_kwargs_out,
		# 		'extradat'             : meta,
		# 		'dispatch_key'         : "rpc-system",
		# 		'response_routing_key' : 'response'
		# 	}

		scls = self.serialize_class(remote_cls)

		instance = local_exec.PluginInterface_RemoteExec()
		resp_tup = instance.call_code(code_struct=scls, **call_kwargs_out)
		jid = self.job_counter
		self.job_counter += 1
		cont_proxy = {
			'jobid' : jid,
			'ret'   : resp_tup
		}

		ret = self.process_response_items([jid], expect_partials, preload_rets=[cont_proxy])
		if not expect_partials:
			ret = next(ret)
		return ret


	def __blocking_dispatch_call_remote(self, remote_cls, call_kwargs, meta=None, expect_partials=False):

		jobid = self.put_job(remote_cls, call_kwargs, meta)
		ret = self.process_response_items([jobid], expect_partials)
		if not expect_partials:
			ret = next(ret)
		return ret


	def blocking_dispatch_call(self, remote_cls, call_kwargs, meta=None, expect_partials=False, local=False):
		if local:
			return self.__blocking_dispatch_call_local(remote_cls=remote_cls, call_kwargs=call_kwargs, meta=meta, expect_partials=expect_partials)
		else:
			# raise RuntimeError
			return self.__blocking_dispatch_call_remote(remote_cls=remote_cls, call_kwargs=call_kwargs, meta=meta, expect_partials=expect_partials)


	def fetch_update_names(self, local=False):
		namelist = self.blocking_dispatch_call(yiff_remote.RemoteExecClass, call_kwargs={'mode' : 'yp_get_names'}, local=local)

		new     = 0
		updated = 0

		self.log.info("Received %s names", len(namelist['creators']))
		# Push the name list into the DB
		with self.db.context_sess() as sess:
			for adict in namelist['creators']:
				name = str(adict['id'])
				res = sess.query(self.db.ScrapeTargets)             \
					.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()

				if not res:
					new += 1
					self.log.info("Need to insert name: %s -> %s", name, adict['name'])
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

	def getNameList(self, update_namelist, local=False):
		if update_namelist:
			self.fetch_update_names(local=local)

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets)                                                                \
				.filter(self.db.ScrapeTargets.site_name == self.targetShortName)                                   \
				.filter(self.db.ScrapeTargets.last_fetched < datetime.datetime.now() - datetime.timedelta(days=7)) \
				.all()

			ret = [(row.id, row.artist_name) for row in res]
			random.shuffle(ret)
			sess.commit()
		self.log.info("Found %s names to fetch", len(ret))
		return ret

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

		if isinstance(filecontent, bytes):
			with open(fqpath, "wb") as fp:
				fp.write(filecontent)
		elif isinstance(filecontent, str):
			with open(fqpath, "w", encoding='utf-8') as fp:
				fp.write(filecontent)
		else:
			self.log.error("Unknown data type: %s", type(filecontent))


		return fqpath

	def save_files(self, sess, arow, prow, attachments):
		have_all = True
		update = False
		for file in attachments:
			if 'fdata' in file:
				urlname = urllib.parse.urlsplit(file['url']).path
				urlfn = os.path.split(urlname)[-1]
				resname = "{} {}".format(file['header_fn'], urlfn).strip()

				aname = "{} - {}".format(arow.id, arow.extra_meta['name'])
				aname = urllib.parse.unquote(aname)
				fqDlPath = self.save_file(aname, resname, file['fdata'])
				self.log.info("Saving file to '%s'", fqDlPath)

				frow = sess.query(self.db.ArtFile) \
					.filter(self.db.ArtFile.item_id == prow.id) \
					.filter(self.db.ArtFile.file_meta == file['url']) \
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
							file_meta = file['url'],
							filename  = resname,
							fspath    = fqDlPath,
						)
					sess.add(frow)
				sess.commit()
				update = True
			elif 'error' in file and file['error']:
				pass
			elif 'skipped' in file and file['skipped']:
				# self.log.info("Skipped file: %s, %s, %s", file['skipped'], file['url'], list(file.keys()))
				pass
			else:
				self.log.error("File missing 'fdata': %s", len(file))
				asstr = str(file)
				if len(asstr) < 100000:
					self.log.error("File info: %s", asstr)
				else:
					self.log.error("File as str is %s bytes long, not printing.", len(asstr))
				have_all = False
				update = True

		ret = 'complete' if have_all else 'error'
		# self.log.info("Save files state: %s", ret)
		return ret, update

	def _process_response_post(self, sess, arow, post_struct):
		sess.expire_all()
		have = sess.query(self.db.ArtItem)                             \
			.filter(self.db.ArtItem.artist_id    == arow.id)           \
			.filter(self.db.ArtItem.release_meta == post_struct['id']) \
			.scalar()
		if have:
			sess.commit()
			# self.log.info("Have post: '%s'", post_struct['title'])
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
			sess.commit()

		if post_struct['attachments']:
			result, update = self.save_files(sess, arow, have, post_struct['attachments'])
			if update:
				self.log.info("Saved attachment result: %s", result)
				have.state = result
			# else:
			# 	self.log.info("Item skipped, not changing row.")
		else:
			if have.state != 'complete':
				have.state = 'complete'
				self.log.info("Post '%s' has no attachments?", post_struct['title'])

		sess.commit()


	def _process_response_file(self, sess, arow, post_struct):

		sess.expire_all()
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

		sess.commit()

		result, update = self.save_files(sess, arow, have, post_struct['attachments'])
		if update:
			self.log.info("Saved file result: %s", result)
			have.state = result
		else:
			self.log.info("Item skipped, not changing row.")

		if not post_struct['attachments']:
			self.log.info("File post '%s' is missing the actual file?", post_struct['title'])
			if have.state != 'complete':
				have.state = 'complete'

		sess.commit()

	def process_resp(self, resp):


		with self.db.context_sess() as sess:
			arow = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == resp['extra_meta']['aid']).one()

		for x in range(50):
			try:
				with self.db.context_sess() as sess:
					if resp['meta']['artist_name'].lower() != arow.extra_meta['name'].lower():
						self.log.error("Artist name mismatch! '%s' -> '%s'", resp['meta']['artist_name'], arow.extra_meta['name'])
						return
					for post in resp['posts'].values():
						self._process_response_post(sess, arow, post)
					for file in resp['files'].values():
						self._process_response_file(sess, arow, file)

					if all([post.state != 'new' for post in arow.posts]):
						arow.last_fetched = datetime.datetime.now()
					sess.commit()

					return

			except sqlalchemy.exc.InvalidRequestError:
				print("InvalidRequest error!")
				sess.rollback()
				traceback.print_exc()
				if x > 10:
					raise
			except sqlalchemy.exc.OperationalError:
				print("Operational error!")
				sess.rollback()
				if x > 10:
					raise
			except sqlalchemy.exc.IntegrityError:
				print("Integrity error!")
				traceback.print_exc()
				sess.rollback()
				if x > 10:
					raise

	def process_retry(self, resp):

		for x in range(10):
			try:
				self.process_resp(resp)
				return
			except sqlalchemy.exc.OperationalError:
				self.log.error("Failure in process_retry - sqlalchemy.exc.OperationalError")

		self.log.error("Failure in process_retry, out of attempts!")

	def trigger_fetch(self, aid, local):

		with self.db.context_sess() as sess:
			arow = sess.query(self.db.ScrapeTargets).filter(self.db.ScrapeTargets.id == aid).one()

		# print(arow, arow.id, arow.site_name, arow.artist_name, arow.extra_meta)
		have = []

		for post in arow.posts:
			if post.state == 'complete':
				for file in post.files:
					if file.file_meta:
						have.append(file.file_meta)

		self.log.info("Have %s items.", len(have))

		if local:
			self.job_map[self.job_counter] = aid
			ret = self.__blocking_dispatch_call_local(
				remote_cls=yiff_remote.RemoteExecClass,
				call_kwargs = {
					'mode'              : 'yp_get_content_for_artist',
					'aid'               : arow.artist_name,
					'have_urls'         : have,
					'yield_chunk'       : 1024 * 1024 * 64 if not local else None,

					# Total chunk limit so things don't fetch for so long the VM rollover causes them to be reset.
					'total_fetch_limit' : 1024 * 1024 * 1048 * 8 if not local else None,

					'extra_meta'        : {'aid' : aid},
				},
				expect_partials=True)

			for resp in ret:
				self.process_retry(resp)
			return None
		else:
			jid = self.put_job(
				remote_cls      = yiff_remote.RemoteExecClass,
				call_kwargs     = {
						'mode'              : 'yp_get_content_for_artist',
						'aid'               : arow.artist_name,
						'have_urls'         : have,
						'yield_chunk'       : 1024 * 1024 * 64 if not local else None,

						# Total chunk limit so things don't fetch for so long the VM rollover causes them to be reset.
						'total_fetch_limit' : 1024 * 1024 * 1048 * 8 if not local else None,

						'extra_meta'        : {'aid' : aid},
					},
				early_ack       = True,
				)
			self.job_map[jid] = aid
			return jid

	def go_test(self):
		jid = self.put_job(
			remote_cls      = yiff_remote.RemoteExecClass,
			call_kwargs     = {
					'mode'              : 'plain_web_get',
					'requestedUrl'      : "http://www.google.com",
					'extra_meta'        : {'aid' : None},
				},
			early_ack       = True,
			)


		for resp in self.process_response_items([jid], True):
			self.log.info("Processing response chunk.")
			self.process_retry(resp)
			self.log.info("Response chunk processed.")
		self.log.info("go_test has completed")

	def do_fetch_by_aids(self, aids, local):

		jobids = [self.trigger_fetch(aid, local) for aid in aids]

		if not any(jobids):
			self.log.warning("No jobid resps?")
			return

		for resp in self.process_response_items(jobids, True):
			self.log.info("Processing response chunk.")
			self.process_retry(resp)
			self.log.info("Response chunk processed.")
		self.log.info("do_fetch_by_aids has completed")


	def go(self, ctrlNamespace=None, update_namelist=True, local=False):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")

		nl = self.getNameList(update_namelist, local)
		if 'drain' in sys.argv:
			nl = nl[:3]

		nl = [
					(aid, aname)
				for
					aid, aname
				in
					nl
				if
					aname.lower()
				not in
					settings[self.settingsDictKey]['masked-users']
					]
		# for chunk in [nl, ]:

		for x in range(10000 if 'drain' in sys.argv else 1):
			for chunk in batch(nl, PARALLEL_JOBS if not local else 1):
				try:
					self.do_fetch_by_aids([aid for aid, _ in chunk], local)
				except Exception:
					for line in traceback.format_exc().split("\n"):
						self.log.error(line)

				if not flags.namespace.run:
					print("Exiting!")
					return

		self.log.info("YiffScrape has finished!")

def mgr_init():
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	print('initialized manager')

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

def local_test():
	import WebRequest
	import bs4
	import sys
	print("Setup")
	wg = WebRequest.WebGetRobust()
	t2 = yiff_remote.RemoteExecClass(wg=wg)
	print("Loading file")
	with open(sys.argv[1], "r") as fp:
		cont=fp.read()
	print("Parsing file")
	soup = bs4.BeautifulSoup(cont, 'lxml')
	print("Extracting")

	r1 = t2.get_meta_from_release_soup(soup)
	r2 = t2.get_posts_from_page(soup)
	r3 = t2.get_files_from_page(soup)

	pprint.pprint(("R1:", r1))
	pprint.pprint(("R2:", r2))
	pprint.pprint(("R2:", r3))

def run_remote():
	import multiprocessing

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	signal.signal(signal.SIGINT, signal_handler)

	print(sys.argv)
	ins = GetYP()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	update_nl = True
	if "no_namelist" in sys.argv:
		update_nl = False
	if "drain" in sys.argv:
		update_nl = False
	if not update_nl:
		print("Not fetching new names from site!")

	# ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	ins.go(ctrlNamespace=flags.namespace, update_namelist=update_nl)


def run_local():
	import multiprocessing

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	signal.signal(signal.SIGINT, signal_handler)

	print(sys.argv)
	ins = GetYP()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	update_nl = True
	if "no_namelist" in sys.argv:
		update_nl = False
	if "drain" in sys.argv:
		update_nl = False
	if not update_nl:
		print("Not fetching new names from site!")

	# ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	ins.go(ctrlNamespace=flags.namespace, update_namelist=update_nl, local=True)

if __name__ == '__main__':

	import sys
	import logSetup
	logSetup.initLogging()

	if 'local' in sys.argv:
		run_local()
	elif len(sys.argv) == 1 or 'drain' in sys.argv or 'no_namelist' in sys.argv:
		run_remote()
	elif 'test_get_filename' in sys.argv:
		ins = GetYP()
		ins.go_test()
	else:
		local_test()




