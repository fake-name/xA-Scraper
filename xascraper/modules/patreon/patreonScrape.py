import os
import os.path
import traceback
import datetime
import pytz
import dateutil.parser
import bs4
import WebRequest
import cloudscraper
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

from . import patreonBase

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

PATREON_LOGIN_PAGE = 'https://www.patreon.com/login'
PATREON_HOME_PAGE  = 'https://www.patreon.com/home'

class GetPatreon(patreonBase.GetPatreonBase):



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def local_save_file(self, aname, filename, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, filename)
		self.save_file(fqfilename=fqpath, file_content=filecontent)

	def save_json(self, aname, itemid, filecontent):
		fdir = self.get_save_dir(aname)
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
		fdir = self.get_save_dir(aname)
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

		fdir = self.get_save_dir(aname)
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

		fdir = self.get_save_dir(aname)
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


	def _get_art_post(self, postId, artistName):
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
			self.log.warning("You apparently cannot view post %s for artist %s. Ignoring.", postId, artistName)
			fail = {
				'status' : ''
				}
			return fail

		if not 'included' in post:
			self.log.warning("No contents on post %s for artist %s (%s). Please report if this is in error.", postId, artistName, post_info['url'])
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

				fpath = self.save_image(artistName, postId, post_info['post_file']['name'], furl)
				files.append(fpath)

			if 'post_type' in post_info and post_info['post_type'] == 'video_embed':
				# print("Post video_embed")
				fpath = self.fetch_video_embed(post_info)
				if fpath:
					files.append(fpath)
				ret['post_embeds'].append(post_info)

			for aid, dat_struct in attachments.items():
				# print("Post attachments")
				fpath = self.save_attachment(artistName, postId, dat_struct)
				files.append(fpath)

			for aid, dat_struct in media.items():
				# print("Post attachments")
				fpath = self.save_media(artistName, postId, dat_struct)
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
				fpath = self.save_image(artistName, postId, fname, furl)
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


	def _getArtPage(self, post_meta, artistName):

		item_type, postid = post_meta

		if item_type == 'post':
			item_key = "{}-{}-{}-fetchtime".format("pat", item_type, postid)
			have = self.db.get_from_db_key_value_store(item_key)

			# If we've fetched it in the last 2 weeks, don't retry it.
			if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*7*2):
				fail = {
					'status' : ''
					}
				return fail

			try:
				ret = self._get_art_post(postid, artistName)
				self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})
				return ret
			except exceptions.ContentRemovedException:
				# Don't retry removed items more then once a year.
				self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time() + 60*60*24 * 365})
				raise

			finally:
				self.random_sleep(1,3,10, include_long=False)



		else:
			self.log.error("Unknown post type: '%s'", item_type)
			raise RuntimeError("Wat?")

	def get_art_item(self, artist_undecoded, artist_name, postid):

		postid_s = json.dumps(postid)

		extends = []

		try:
			ret = self._fetch_retrier(postid, artist_name)

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
							release_meta       = json.dumps(postid),
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
				self._updateUnableToRetrieve(artist_undecoded, postid_s)

		except urllib.error.URLError:  # WebGetRobust throws urlerrors
			self.log.error("Page Retrieval failed!")
			self.log.error("PostID = '%s'", postid)
			self.log.error(traceback.format_exc())
		except:
			self.log.error("Unknown error in page retrieval!")
			self.log.error("PostID = '%s'", postid)
			self.log.error(traceback.format_exc())

			import IPython
			IPython.embed()

		return extends


	def _load_art(self, campaign_id, artist_undecoded, artist_name):
		local_aid = self._artist_name_to_rid(artist_undecoded)

		item_key = "{}-{}-{}-fetchtime".format("pat", "content_list_fetch", local_aid)
		have = self.db.get_from_db_key_value_store(item_key)

		# If we've fetched the parts list in the last 2 day, skip it.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*2):
			pass

		else:

			oldArt = self._getPreviouslyRetreived(artist_undecoded)
			artPages = self.get_campaign_posts(local_aid, campaign_id, artist_undecoded, artist_name, oldArt)
			self.log.info("Total gallery items %s", len(artPages))

			new = 0
			with self.db.context_sess() as sess:
				for item in artPages:
					item_json = json.dumps(item, sort_keys=True)
					new += self._upsert_if_new(sess, local_aid, item_json)

			self.log.info("%s new art pages, %s total", new, len(artPages))

			newArt = artPages - oldArt
			self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})


		new_raw = self._getNewToRetreive(aid=local_aid)

		return [json.loads(tmp) for tmp in new_raw]



	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")
		is_another_active = self.getRunningStatus(self.pluginShortName)

		if is_another_active:
			self.log.error("Another instance of the %s scraper is running.", self.pluginShortName)
			self.log.error("Not starting")
			return
		try:
			self.updateRunningStatus(self.pluginShortName, True)
			startTime = datetime.datetime.now()
			self.updateLastRunStartTime(self.pluginShortName, startTime)

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.info("Do not have login cookie. Retreiving one now.")
				cookieStatus, msg = self.getCookie()
				self.log.info("Login attempt status = %s (%s).", cookieStatus, msg)
				assert cookieStatus, "Login failed! Cannot continue!"

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.critical("Failed to download cookie! Exiting!")
				return False

			if not nameList:
				nameList = self.getNameList()

			errored = False

			# Farm out requests to the thread-pool
			with concurrent.futures.ThreadPoolExecutor(max_workers=self.numThreads) as executor:

				future_to_url = {}
				for aId, aName in nameList:
					future_to_url[executor.submit(self.getArtist, aName, ctrlNamespace)] = aName

				for future in concurrent.futures.as_completed(future_to_url):
					# aName = future_to_url[future]
					res = future.result()
					if type(res) is not bool:
						raise RuntimeError("Future for plugin %s returned non-boolean value (%s). Function %s of class %s" % (self.pluginShortName, res, self.getArtist, self))
					errored  |= future.result()
					# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

			if errored:
				self.log.warn("Had errors!")

			runTime = datetime.datetime.now()-startTime
			self.updateLastRunDuration(self.pluginShortName, runTime)

		finally:
			self.updateRunningStatus(self.pluginShortName, False)


	def getArtist(self, artist_undecoded, ctrlNamespace):
		artist_meta = json.loads(artist_undecoded)
		artist_name, artist_meta = artist_meta

		# Fix artists with leading/trailing spaces
		artist_name = artist_name.strip()

		if ctrlNamespace.run is False:
			# self.log.warning("Exiting early from %s due to run flag being unset", artist_undecoded)
			return True

		try:
			self.log.info("GetArtist - %s -> %s", artist_name, artist_undecoded)
			# check if setting exists
			if 'blacklisted_artists' in settings[self.pluginShortName]:
			# check the names here and only add if in configured array
				if artist_name in settings[self.pluginShortName]['blacklisted_artists']:
					self.log.info("skipping: %s  by name as it is configured in blacklist", artist_name)
					return False
			# check if setting exists
			if 'blacklisted_artists_ids' in settings[self.pluginShortName]:
				if patreon_aid in settings[self.pluginShortName]['blacklisted_artists_ids']:
					self.log.info("skipping: %s by id as it is configured in blacklist", artist_name)
					return False
			self.setupDir(artist_name)

			if 'campaign' in artist_meta and artist_meta['campaign']['data']['type'] == 'campaign':
				campaign_id = artist_meta['campaign']['data']['id']

				newArt = self._load_art(campaign_id, artist_undecoded, artist_name)
			else:
				newArt = []


			embeds = []


			while len(newArt) > 0:
				postid = newArt.pop()

				ret = self.get_art_item(artist_undecoded, artist_name, postid)
				embeds.extend(ret)


				self.log.info("Pages for %s remaining = %s", artist_name, len(newArt))
				if ctrlNamespace.run is False:
					break

			self.update_last_fetched(artist_undecoded)
			self.log.info("Successfully retreived content for artist %s", artist_name)

			if embeds:
				self.log.info("Dumping item embeds to pyson file")
				self.save_embeds(artist_name, embeds)

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
			self.log.error("Exception when retreiving artist %s", artist_name)
			self.log.error("%s", traceback.format_exc())
			return True



	def save_embeds(self, aname, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, 'post-embeds.pyson')
		with open(fqpath, "wb") as fp:
			fstr = pprint.pformat(filecontent)
			fp.write(fstr.encode("utf-8"))


	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_artist_lut(self):
		general_meta = self.current_user_info()
		campaign_items = [item for item in general_meta['included'] if item['type'] == "campaign"]
		artist_lut = [(item['attributes']['full_name'].strip(), item['relationships']) for item in general_meta['included'] if item['type'] == 'user']

		return artist_lut

	def getNameList(self):
		self.log.info("Getting list of favourite artists.")

		try:

			artist_lut = self.get_artist_lut()
		except Exception as e:
			import IPython
			IPython.embed()


		self.log.info("Found %d Names", len(artist_lut))
		for value in artist_lut:
			print(value)

		resultList = [json.dumps(value, sort_keys=True) for value in artist_lut]


		with self.db.context_sess() as sess:
			for name in resultList:
				# check if setting exists
				if 'blacklisted_artists' in settings[self.pluginShortName]:
				# check the names here and only add if in configured array
					if name[1][0] in settings[self.pluginShortName]['blacklisted_artists']:
						self.log.info("skipping: %s", name[1][0])
						continue
				# check if setting exists
				if 'blacklisted_artists_ids' in settings[self.pluginShortName]:
					if name[0] in settings[self.pluginShortName]['blacklisted_artists_ids']:
						self.log.info("skipping: %s", name[1][0])
						continue
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()
				if not res:
					self.log.info("Need to insert name: %s", name)
					sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name))
					sess.commit()

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets)             \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.all()

			for row in res:
				if row.artist_name in resultList:
					if not row.enabled:
						self.log.info("Enabling artist: %s", row.artist_name)
						row.enabled = True
				else:
					if row.enabled:
						self.log.info("Disabling artist: %s", row.artist_name)
						row.enabled = False

			sess.commit()



		return super().getNameList()



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_campaign_posts(self, local_aid, campaign_id, artist_undecoded, artist_name, oldArt):
		now = datetime.datetime.utcnow().replace(tzinfo = pytz.utc).replace(microsecond=0)

		postids = set()
		types = ['posts', 'poll']

		api_page_url = "/posts?" + \
				"include=user%2Cattachments%2Ccampaign%2Cpoll.choices%2Cpoll.current_user_responses.user%2Cpoll.current_user_responses.choice%2Cpoll.current_user_responses.poll%2Caccess_rules.tier.null%2Cimages.null%2Caudio.null" + \
				"&fields[post]=change_visibility_at%2Ccomment_count%2Ccontent%2Ccurrent_user_can_delete%2Ccurrent_user_can_view%2Ccurrent_user_has_liked%2Cembed%2Cimage%2Cis_paid%2Clike_count%2Cmin_cents_pledged_to_view%2Cpost_file%2Cpost_metadata%2Cpublished_at%2Cpatron_count%2Cpatreon_url%2Cpost_type%2Cpledge_url%2Cthumbnail_url%2Cteaser_text%2Ctitle%2Cupgrade_url%2Curl%2Cwas_posted_by_campaign_owner" + \
				"&fields[user]=image_url%2Cfull_name%2Curl" + \
				"&fields[campaign]=show_audio_post_download_links%2Cavatar_photo_url%2Cearnings_visibility%2Cis_nsfw%2Cis_monthly%2Cname%2Curl" + \
				"&fields[access_rule]=access_rule_type%2Camount_cents" + \
				"&fields[media]=id%2Cimage_urls%2Cdownload_url%2Cmetadata%2Cfile_name" + \
				"&sort=-published_at" + \
				"&filter[is_draft]=false&filter[contains_exclusive_posts]=true&json-api-use-default-includes=false&json-api-version=1.0" + \
				"&filter[campaign_id]={campaign_id}".format(campaign_id=campaign_id)

		while api_page_url:
			current = self.get_api_json(api_page_url)

			if not "data" in current:
				import IPython
				IPython.embed()


			had_post = False
			for release in current['data']:
				if release['type'] == "post" or release['type'] == "poll":
					postdate = dateutil.parser.parse(release['attributes']['published_at'])
					postid   = release['id']

					if postdate < now:
						now = postdate


					post_tup = (release['type'], postid)
					if not post_tup in postids:
						postids.add(post_tup)
						had_post = True


					# post_s = json.dumps(post_tup)

					# if post_s not in oldArt:
					# 	print("New post:", post_s)
					# 	self.get_art_item(artist_undecoded, artist_name, post_tup)

					# 	with self.db.context_sess() as sess:
					# 		item_json = json.dumps(post_tup, sort_keys=True)
					# 		self._upsert_if_new(sess, local_aid, item_json)

					if release['type'] != "post":
						self.log.warning("Non post release!")

				else:
					self.log.warning("Unknown type!")
					for line in pprint.pformat(release).split("\n"):
						self.log.warning(line)


			self.log.info("iterating over listing of campaign posts. Found %s so far, have new: %s.", len(postids), had_post)

			if 'links' in current and 'next' in current['links']:
				api_page_url = current['links']['next']
			else:
				api_page_url = None


			self.random_sleep(2,4,15, include_long=False)

		return postids



	def run_old(self):
		self.check_login()
		# self.get_pledges()
		self.fetch_all()

	def go(self, *args, **kwargs):

		self.cr = ChromeController.ChromeRemoteDebugInterface(
				binary             = "google-chrome",
				headless           = False,
				enable_gpu         = True,
				additional_options = ['--new-window']
			)

		super().go(*args, **kwargs)

def signal_handler(dummy_signal, dummy_frame):
	import flags
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
	ins = GetPatreon()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	# ins.go(ctrlNamespace=flags.namespace)


if __name__ == '__main__':

	import sys
	import logSetup
	import logging
	logSetup.initLogging(logLevel=logging.DEBUG)

	run_local()
