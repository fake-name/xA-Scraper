import os
import os.path
import traceback
import datetime
import pytz
import dateutil.parser
import bs4
import WebRequest
import tqdm
import urllib.parse
import json
import time
import random
import pprint
import requests
import ChromeController
from settings import settings

import xascraper.modules.scraper_base
from xascraper.modules import exceptions


class GetKemono(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "kemono"

	pluginName = "KemonoGet"

	urlBase = None

	ovwMode = "Check Files"

	numThreads = 1


	# Stubbed functions
	_getGalleries = None
	_getTotalArtCount = None

	extra_wg_params = {"chromium_headless" : False}

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


		# This is.... kind of horrible.
		self.wg.errorOutCount = 1



	def get_soup(self, url):
		# resp = self.req.get(url)
		# assert 'text/html' in resp.headers.get("content-type", ""), "response isn't text/html, it's %s" % resp.headers.get("content-type")
		# return WebRequest.as_soup(resp.text)

		self.cr.blocking_navigate(url)
		content = self.cr.get_rendered_page_source()

		return WebRequest.as_soup(content)

	def checkCookie(self):
		return True, "No Auth"


	def getCookie(self):
		if self.checkCookie()[0]:
			return True, "Already logged in"


	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_save_dir(self, kemono_service, kemono_name):

		dirp = self.getDownloadPath(self.dlBasePath, os.path.join(kemono_service, kemono_name))
		if not os.path.exists(dirp):
			os.makedirs(dirp)
		return dirp

	def local_save_file(self, aname, filename, filecontent):
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, filename)
		self.save_file(fqfilename=fqpath, file_content=filecontent)

	def save_json(self, aname, itemid, filecontent):
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, "pyson-posts")
		if not os.path.exists(fqpath):
			os.makedirs(fqpath)
		fqpath = os.path.join(fqpath, 'itemid-{id}.pyson'.format(id=itemid))
		with open(fqpath, "wb") as fp:
			fstr = pprint.pformat(filecontent)
			fp.write(fstr.encode("utf-8"))

	def save_image(self, aname, pid, fname, furl):
		print("Saving image: '%s'" % furl)
		fname = "{pid}-{fname}".format(pid=pid, fname=fname)
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, fname)
		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			try:
				content = self.wg.getpage(furl, addlHeaders={"Referer" : PATREON_HOME_PAGE})
			except WebRequest.FetchFailureError:
				self.log.error(traceback.format_exc())
				self.log.error("Could not retreive content: ")
				self.log.error("%s", furl)
				return None

			if content:
				self.local_save_file(aname, fname, content)
			else:
				self.log.error("Could not retreive content: ")
				self.log.error("%s", furl)
				return None
		return fqpath

	def save_attachment(self, aname, pid, dat_struct):
		print("Saving attachment: '%s'" % dat_struct['attributes']['url'])
		if dat_struct['attributes']['url'].startswith("https"):
			url = dat_struct['attributes']['url']
		else:
			url = "https:{url}".format(url=dat_struct['attributes']['url'])

		fname = "{pid}-{aid}-{fname}".format(pid=pid, aid=dat_struct['id'], fname=dat_struct['attributes']['name'])

		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, fname)

		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			content = self.wg.getpage(url, addlHeaders={"Referer" : PATREON_HOME_PAGE})
			if content:
				if isinstance(content, str):
					with open(fqpath, "wb") as fp:
						fp.write(content.encode("utf-8"))
				else:
					with open(fqpath, "wb") as fp:
						fp.write(content)
			else:
				return None

		return fqpath


	def save_media(self, aname, pid, dat_struct):
		print("Saving media item: '%s'" % dat_struct['attributes']['download_url'])
		if dat_struct['attributes']['download_url'].startswith("https"):
			url = dat_struct['attributes']['download_url']
		else:
			url = "https:{url}".format(url=dat_struct['attributes']['download_url'])


		fname = str(dat_struct['attributes']['file_name']).split("/")[-1]
		fname = "{pid}-{aid}-{fname}".format(pid=pid, aid=dat_struct['id'], fname=fname)

		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, fname)

		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			try:
				content = self.wg.getpage(url, addlHeaders={"Referer" : PATREON_HOME_PAGE})
			except WebRequest.FetchFailureError:
				self.log.error(traceback.format_exc())
				self.log.error("Could not retreive content: ")
				self.log.error("%s", url)
				return None
			if content:
				if isinstance(content, str):
					self.local_save_file(aname, fname, content.encode("utf-8"))
				else:
					self.local_save_file(aname, fname, content)
			else:
				return None

		return fqpath



	# TODO: Implement this
	def fetch_video_embed(self, post_content):
		self.log.warning("Embedded video. Plz complain on github about this!")
		return None

	def _handle_embed(self, embed_info):
		self.log.warning("Embedded external content. Plz complain on github about this!")
		self.log.warning("Include the above json-like output so I can see what I need to do.")
		return []


	def _getContentUrlFromPage(self, soup):

		dlBar = soup.find('ul', id='detail-actions')


		dummy, dlLink, dummy = dlBar.find_all('li')
		if 'Download' in dlLink.get_text():
			itemUrl = urllib.parse.urljoin(self.urlBase, dlLink.a['href'])

			return itemUrl

		raise ValueError("Wat?")

	def __handle_errors(self, post_errors):
		for error in post_errors:
			if 'code_name' in error and error['code_name'] == 'ResourceMissing' and 'status' in error and error['status'] == '404':
				raise exceptions.ContentRemovedException("Item has been deleted or removed.")


	def _get_art_post(self, postId, kemono_service, kemono_name):
		post = self.get_api_json("/posts/{pid}".format(pid=postId) +
			"?include=media"
			)

		if 'status' in post and post['status'] == '404':
			self.log.warning("Post is not found!")
			fail = {
				'status' : ''
				}
			return fail


		if not 'data' in post:
			if "errors" in post:
				self.__handle_errors(post['errors'])

			self.log.warning("No 'data' member in post!")

			pprint.pprint(post)
			fail = {
				'status' : ''
				}
			return fail


		post_content = post['data']
		post_info = post_content['attributes']

		if 'current_user_can_view' in post_info and post_info['current_user_can_view'] is False:
			self.log.warning("You apparently cannot view post %s for artist %s. Ignoring.", postId, kemono_service, kemono_name)
			fail = {
				'status' : ''
				}
			return fail

		if not 'included' in post:
			self.log.warning("No contents on post %s for artist %s (%s). Please report if this is in error.", postId, kemono_service, kemono_name, post_info['url'])
			fail = {
				'status' : ''
				}
			return fail


		attachments = {item['id'] : item for item in post['included'] if item['type'] == 'attachment'}
		media       = {item['id'] : item for item in post['included'] if item['type'] == 'media'}

		tags = []
		if 'user_defined_tags' in post_content['relationships']:
			for tagmeta in post_content['relationships']['user_defined_tags']['data']:
				tags.append(tagmeta['id'].split(";")[-1])

		if 'current_user_can_view' in post_content and not post_content['current_user_can_view']:
			raise exceptions.CannotAccessException("You can't view that content!")

		# if not 'content' in post_info:
		# pprint.pprint(post_content)

		ret = {
			'page_desc'   : post_info['content'],
			'page_title'  : post_info['title'],
			'post_time'   : dateutil.parser.parse(post_info['published_at']).replace(tzinfo=None),
			'post_tags'   : tags,
			'post_embeds' : [],
		}

		# print("Post:")
		# pprint.pprint(post)
		# print("Content:")
		# pprint.pprint(post_info['content'])

		files = []
		try:
			if "post_file" in post_info and post_info['post_file']:
				furl = urllib.parse.unquote(post_info['post_file']['url'])
				# print("Post file!", post_info['post_file']['url'], furl)

				fpath = self.save_image(kemono_service, kemono_name, postId, post_info['post_file']['name'], furl)
				files.append(fpath)

			if 'post_type' in post_info and post_info['post_type'] == 'video_embed':
				# print("Post video_embed")
				fpath = self.fetch_video_embed(post_info)
				if fpath:
					files.append(fpath)
				ret['post_embeds'].append(post_info)

			for aid, dat_struct in attachments.items():
				# print("Post attachments")
				fpath = self.save_attachment(kemono_service, kemono_name, postId, dat_struct)
				files.append(fpath)

			for aid, dat_struct in media.items():
				# print("Post attachments")
				fpath = self.save_media(kemono_service, kemono_name, postId, dat_struct)
				files.append(fpath)

			if 'embed' in post_info and post_info['embed']:
				for item in self._handle_embed(post_info['embed']):
					files.append(fpath)
				ret['post_embeds'].append(post_info['embed'])




		except urllib.error.URLError:
			self.log.error("Failure retreiving content from post: %s", post)

		# Posts can apparently be empty.
		if not post_info['content']:
			post_info['content'] = ""

		ctnt_soup = bs4.BeautifulSoup(post_info['content'], 'lxml')

		for img in ctnt_soup.find_all("img", src=True):
			furl = img['src']
			fparsed = urllib.parse.urlparse(furl)
			fname = fparsed.path.split("/")[-1]

			# Somehow empty urls ("http://") are getting into here.
			if len(furl) > len("https://xx"):
				fpath = self.save_image(kemono_service, kemono_name, postId, fname, furl)
				files.append(fpath)

		# Youtube etc are embedded as iframes.
		for ifr in ctnt_soup.find_all("iframe", src=True):
			ret['post_embeds'].append(ifr['src'])


		if len(files):
			self.log.info("Found %s images/attachments on post.", len(attachments))
		else:
			self.log.warning("No images/attachments on post %s!", postId)


		files = [filen for filen in files if filen]
		ret['dl_path'] = files
		ret['status']  = 'Succeeded'

		# pprint.pprint(ret)
		return ret


	def _getArtPage(self, post_url, kemono_service, kemono_name):

		item_key = "{}-{}-fetchtime".format("kemono", post_url)

		have = self.db.get_from_db_key_value_store(item_key)

		# If we've fetched it in the last 2 weeks, don't retry it.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*7*2):
			fail = {
				'status' : ''
				}
			return fail

		try:
			ret = self._get_art_post(post_url, kemono_service, kemono_name)
			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})
			return ret
		except exceptions.ContentRemovedException:
			# Don't retry removed items more then once a year.
			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time() + 60*60*24 * 365})
			raise

		finally:
			self.random_sleep(1,3,10, include_long=False)


	def get_art_item(self, artist_undecoded, kemono_service, kemono_name, post_url):

		extends = []

		try:
			ret = self._fetch_retrier(post_url, kemono_service, kemono_name)

			assert isinstance(ret, dict), "Response is not a dict?"
			assert 'status'     in ret, "Status not in response!"

			if 'post_embeds' in ret:
				extends = ret['post_embeds']


			if ret['status'] == "Succeeded" or ret['status'] == "Exists":

				assert 'dl_path'    in ret
				assert 'page_desc'  in ret
				assert 'page_title' in ret
				assert 'post_time'  in ret
				assert 'post_tags'  in ret

				assert isinstance(ret['dl_path'], list)
				seq = 0
				for item in ret['dl_path']:
					self._updatePreviouslyRetreived(
							artist             = artist_undecoded,
							state              = 'complete',
							release_meta       = post_url,
							fqDlPath           = item,
							pageDesc           = ret['page_desc'],
							pageTitle          = ret['page_title'],
							seqNum             = seq,
							addTime            = ret['post_time'],
							postTags           = ret['post_tags'],
							content_structured = ret,
						)
					seq += 1
			elif ret['status'] == "Ignore":  # Used for compound pages (like Pixiv's manga pages), where the page has multiple sub-pages that are managed by the plugin
				self.log.info("Ignoring root URL, since it has child-pages.")
			else:
				self._updateUnableToRetrieve(artist_undecoded, post_url)

		except urllib.error.URLError:  # WebGetRobust throws urlerrors
			self.log.error("Page Retrieval failed!")
			self.log.error("PostID = '%s'", post_url)
			self.log.error(traceback.format_exc())
		except:
			self.log.error("Unknown error in page retrieval!")
			self.log.error("PostID = '%s'", post_url)
			self.log.error(traceback.format_exc())

			import IPython
			IPython.embed()

		return extends


	def _load_art(self, artist_undecoded, kemono_service, kemono_aid):
		local_aid = self._artist_name_to_rid(artist_undecoded)

		item_key = "{}-{}-{}-fetchtime".format("kemono", "content_list_fetch", local_aid)
		have = self.db.get_from_db_key_value_store(item_key)


		# If we've fetched it in the last 2 weeks, don't retry it.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*7*2):
			pass

		else:
			oldArt = self._getPreviouslyRetreived(artist_undecoded)
			artPages = self.load_art_pages(local_aid,artist_undecoded, kemono_service, kemono_aid)
			self.log.info("Total gallery items %s", len(artPages))

			new = 0
			with self.db.context_sess() as sess:
				for item in artPages:
					new += self._upsert_if_new(sess, local_aid, item)

			self.log.info("%s new art pages, %s total", new, len(artPages))

			newArt = artPages - oldArt
			self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})



		return self._getNewToRetreive(aid=local_aid)

	def getArtist(self, artist_undecoded, ctrlNamespace):



		artist_decoded = json.loads(artist_undecoded)


		kemono_aid     = artist_decoded['id']
		kemono_name    = artist_decoded['name']
		kemono_service = artist_decoded['service']


		if ctrlNamespace.run is False:
			# self.log.warning("Exiting early from %s due to run flag being unset", artist_undecoded)
			return True

		try:
			self.log.info("GetArtist - %s:%s -> %s", kemono_service, kemono_name, artist_undecoded)
			self.setupDir(os.path.join(kemono_service, kemono_name))

			newArt = self._load_art(artist_undecoded, kemono_service, kemono_aid)


			embeds = []


			while len(newArt) > 0:
				post_url = newArt.pop()

				ret = self.get_art_item(artist_undecoded, kemono_service, kemono_name, post_url)
				embeds.extend(ret)


				self.log.info("Pages for %s remaining = %s", kemono_name, len(newArt))
				if ctrlNamespace.run is False:
					break

			self.update_last_fetched(artist_undecoded)
			self.log.info("Successfully retreived content for artist %s:%s", kemono_service, kemono_name)

			if embeds:
				self.log.info("Dumping item embeds to pyson file")
				self.save_embeds(kemono_service, kemono_name, embeds)

			return False

		except exceptions.AccountDisabledException:
			self.log.error("Artist seems to have disabled their account!")
			return False
		except (WebRequest.FetchFailureError, exceptions.UnrecoverableFailureException):
			self.log.error("Unrecoverable exception!")
			self.log.error(traceback.format_exc())
			ctrlNamespace.run = False
			return False

		except:
			self.log.error("Exception when retreiving artist %s:%s", kemono_service, kemono_name)
			self.log.error("%s", traceback.format_exc())
			return True



	def save_embeds(self, kemono_service, kemono_name, filecontent):
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, 'post-embeds.pyson')
		with open(fqpath, "wb") as fp:
			fstr = pprint.pformat(filecontent)
			fp.write(fstr.encode("utf-8"))


	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_artist_listing(self):
		creators_api_endpoint = "https://kemono.party/api/creators"

		creators = self.wg.getJson(creators_api_endpoint)


		artist_lut = [
			{
				"id"      : tmp['id'],
				"name"    : tmp['name'].strip(),
				"service" : tmp['service'].strip(),
			}
			for tmp in creators
		]

		# TODO: Filter so we only re-scrape new people.

		# {'favorited': 237,
		#  'id': '3933678',
		#  'indexed': 1599358964.273816,
		#  'name': 'corvidius',
		#  'service': 'patreon',
		#  'updated': 1659332444.394558}

		return artist_lut

	def getNameList(self):

		try:
			artist_lut = self.get_artist_listing()
		except Exception as e:
			import IPython
			IPython.embed()

		self.log.info("Found %d Names", len(artist_lut))

		resultList = [json.dumps(tmp, sort_keys=True) for tmp in artist_lut]


		with self.db.context_sess() as sess:
			for name in tqdm.tqdm(resultList):
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()
				if not res:
					self.log.info("Need to insert name: %s", name)
					sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name))
					sess.commit()

			sess.commit()



		return super().getNameList()



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def load_art_pages(self, local_aid, artist_undecoded, kemono_service, kemono_aid):
		now = datetime.datetime.utcnow().replace(tzinfo = pytz.utc).replace(microsecond=0)


		art_listing_url = "https://kemono.party/{service}/user/{aid}?o={offset}"


		post_articles = set()

		for offset in range(0, 99999999, 50):
			soup = self.wg.getSoup(art_listing_url.format(service=kemono_service, aid=kemono_aid, offset=offset))

			articles = soup.find_all("article")

			if not articles:
				break



			for article in articles:

				if not article.a:
					import IPython
					IPython.embed()

				post_url = urllib.parse.urljoin(art_listing_url, article.a['href'])

				post_articles.add(post_url)

			self.log.info("iterating over listing of posts. Found %s so far.", len(post_articles))


			self.random_sleep(2,4,15, include_long=False)

		return post_articles



	def run_old(self):
		self.check_login()
		# self.get_pledges()
		self.fetch_all()

	def go(self, *args, **kwargs):

		# self.cr = ChromeController.ChromeRemoteDebugInterface(
		# 		headless           = False,
		# 		enable_gpu         = True,
		# 		additional_options = ['--new-window']
		# 	)
		super().go(*args, **kwargs)

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt


def run_local():
	import multiprocessing
	import flags
	import signal

	manager = multiprocessing.Manager()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	signal.signal(signal.SIGINT, signal_handler)

	print(sys.argv)
	ins = GetKemono()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	# ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	# ins.go(ctrlNamespace=flags.namespace)


if __name__ == '__main__':

	import sys
	import logSetup
	import logging
	logSetup.initLogging(logLevel=logging.DEBUG)

	run_local()
