import os
import os.path
import traceback
import datetime
import concurrent.futures
import urllib.parse
import json
import time
import pprint
import pytz
import dateutil.parser
import bs4
import WebRequest
import ChromeController
import tqdm

import xascraper.modules.scraper_base
from xascraper.modules import exceptions


class GetKemono(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "kemono"

	pluginName = "KemonoGet"

	urlBase = None

	ovwMode = "Check Files"

	numThreads = 2


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

	def local_save_file(self, kemono_service, kemono_name, filename, filecontent):
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, filename)
		self.save_file(fqfilename=fqpath, file_content=filecontent)
		return fqpath

	def save_json(self, kemono_service, kemono_name, itemid, filecontent):
		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, "pyson-posts")
		if not os.path.exists(fqpath):
			os.makedirs(fqpath)
		fqpath = os.path.join(fqpath, 'itemid-{id}.pyson'.format(id=itemid))
		with open(fqpath, "wb") as fp:
			fstr = pprint.pformat(filecontent)
			fp.write(fstr.encode("utf-8"))

	def save_content(self, kemono_service, kemono_name, referrer, source_name, cdn_url):

		cdn_name = urllib.parse.urlsplit(cdn_url).path.split("/")[-1]

		src_fname, _        = os.path.splitext(source_name)
		cdn_fname, cdn_fext = os.path.splitext(cdn_name)

		print("Saving image: '%s'" % cdn_url)
		fname = "{src}-{cdn}{ext}".format(src=src_fname, cdn=cdn_fname, ext=cdn_fext)

		fdir = self.get_save_dir(kemono_service, kemono_name)
		fqpath = os.path.join(fdir, fname)
		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			try:
				if referrer:
					content = self.wg.getpage(cdn_url, addlHeaders={"Referer" : referrer})
				else:
					content = self.wg.getpage(cdn_url)

			except WebRequest.FetchFailureError:
				self.log.error(traceback.format_exc())
				self.log.error("Could not retreive content: ")
				self.log.error("%s", cdn_url)
				return None

			if content:

				if isinstance(content, str):
					content = content.encode("utf-8")

				fqpath = self.local_save_file(kemono_service, kemono_name, fname, content)
				self.random_sleep(2,4,15, include_long=False)
			else:
				self.log.error("Could not retreive content: ")
				self.log.error("%s", cdn_url)
				return None

		return fqpath



	def save_media(self, kemono_service, kemono_name, post_url, dat_struct):
		print("Saving media item: '%s'" % dat_struct['attributes']['download_url'])
		if dat_struct['attributes']['download_url'].startswith("https"):
			url = dat_struct['attributes']['download_url']
		else:
			url = "https:{url}".format(url=dat_struct['attributes']['download_url'])


		fname = str(dat_struct['attributes']['file_name']).split("/")[-1]
		fname = "{pid}-{aid}-{fname}".format(pid=post_url, aid=dat_struct['id'], fname=fname)

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


	def _get_discord_post(self, post_url, kemono_service, kemono_name):


		content_structured = self.get_content_structured(post_url)
		source_url = content_structured['referring_url']

		files = []
		external_embeds = []

		for attachment in content_structured.get('attachments', []):

			attachment_url = urllib.parse.urljoin(source_url, attachment['path'])

			fpath = self.save_content(
					kemono_service = kemono_service,
					kemono_name    = kemono_name,
					referrer       = None,
					source_name    = attachment['name'],
					cdn_url        = attachment_url,
				)

			files.append(fpath)



		for embed in content_structured.get('embeds', []):
			external_embeds.append(embed['url'])

		parsed_post_time = dateutil.parser.parse(content_structured['published']).replace(tzinfo=None)



		post_title = "{server} -> {channel} -> {datetime} : {user}".format(
						server   = kemono_name,
						channel  = content_structured['channel_name'],
						datetime = content_structured['published'],
						user     = content_structured['author']['username']
			)


		out_soup = bs4.BeautifulSoup()

		p_tag = out_soup.new_tag("p")
		p_tag.string = content_structured['content']

		out_soup.append(p_tag)

		for embed in content_structured.get('embeds', []):

			p_tag = out_soup.new_tag("p")
			a_tag = out_soup.new_tag("a", href=embed['url'])

			a_tag.string = embed.get("description", "No Description")
			p_tag.append(a_tag)

			out_soup.append(p_tag)

		files = list(set(files))

		if len(files):
			self.log.info("Found %s images/attachments on post.", len(files))
		else:
			self.log.warning("No images/attachments on post %s!", post_url)


		files = [filen for filen in files if filen]

		ret = {
			'page_desc'   : out_soup.prettify(),
			'page_title'  : post_title,
			'post_time'   : parsed_post_time,
			'post_tags'   : [],  # I don't think there are tags on Kemono?
			'post_embeds' : external_embeds,
			'dl_path'     : files,
			'status'      : 'Succeeded',
		}

		# pprint.pprint(ret)
		return ret


	def _get_art_post(self, post_url, kemono_service, kemono_name):

		# Funky special-case for kemono's discord archiving
		if post_url.startswith("kemono:discord:"):
			return self._get_discord_post(post_url, kemono_service, kemono_name)

		post_url = post_url.replace("https://kemono.party/", "https://kemono.su/")


		soup = self.wg.getSoup(post_url)

		try:

			post_files    = soup.find("div", class_='post__files')

			files = []
			external_embeds = []
			if post_files:
				for pfile in post_files.find_all("a"):
					dl_filename = pfile.get("download")
					file_url = urllib.parse.urljoin('https://kemono.su/', pfile['href'])

					if dl_filename:
						fpath = self.save_content(kemono_service, kemono_name, post_url, dl_filename, file_url)
						files.append(fpath)

					# No download attrigute probably means externally hosted?
					else:
						external_embeds.append(file_url)


			# From what I can tell, videos are also listed in the attachments section.
			# At least a quick check shows that the file ties to the video player is also
			# present as a download.
			post_attachments   = soup.find("ul", class_='post__attachments')

			if post_attachments:
				for pfile in post_attachments.find_all("a"):
					dl_filename = pfile.get("download")
					attachment_url = urllib.parse.urljoin('https://kemono.su/', pfile['href'])

					if dl_filename:

						fpath = self.save_content(kemono_service, kemono_name, post_url, pfile['download'], attachment_url)
						files.append(fpath)
					else:
						fpath = self.save_content(kemono_service, kemono_name, post_url, "unknown.bin", attachment_url)

			# try:
			# 	if "post_file" in post_info and post_info['post_file']:
			# 		furl = urllib.parse.unquote(post_info['post_file']['url'])
			# 		# print("Post file!", post_info['post_file']['url'], furl)

			# 		fpath = self.save_image(kemono_service, kemono_name, post_url, post_info['post_file']['name'], furl)
			# 		files.append(fpath)

			# 	if 'post_type' in post_info and post_info['post_type'] == 'video_embed':
			# 		# print("Post video_embed")
			# 		fpath = self.fetch_video_embed(post_info)
			# 		if fpath:
			# 			files.append(fpath)
			# 		ret['post_embeds'].append(post_info)

			# 	for aid, dat_struct in attachments.items():
			# 		# print("Post attachments")
			# 		fpath = self.save_attachment(kemono_service, kemono_name, post_url, dat_struct)
			# 		files.append(fpath)

			# 	for aid, dat_struct in media.items():
			# 		# print("Post attachments")
			# 		fpath = self.save_media(kemono_service, kemono_name, post_url, dat_struct)
			# 		files.append(fpath)

			# 	if 'embed' in post_info and post_info['embed']:
			# 		for item in self._handle_embed(post_info['embed']):
			# 			files.append(fpath)
			# 		ret['post_embeds'].append(post_info['embed'])


			# except urllib.error.URLError:
			# 	self.log.error("Failure retreiving content from post: %s", post)


			for ad in soup.find_all("div", class_='ad-container'):
				ad.decompose()

			post_title    = soup.find("h1",  class_='post__title')
			post_body     = soup.find("div", class_='post__body')
			post_comments = soup.find("div", class_='post__comments')
			post_time     = soup.find("div", class_='post__published')

			tags = []
			# if 'user_defined_tags' in post_content['relationships']:
			# 	for tagmeta in post_content['relationships']['user_defined_tags']['data']:
			# 		tags.append(tagmeta['id'].split(";")[-1])


			out_soup = bs4.BeautifulSoup()

			out_soup.append(post_body)
			out_soup.append(post_comments)

			if post_time:
				post_time_str = post_time.get_text().replace("Published:", "").strip()
				parsed_post_time = dateutil.parser.parse(post_time_str).replace(tzinfo=None)
			else:
				# Gumroad content does not have a post date.
				parsed_post_time = datetime.datetime.now().replace(tzinfo=None)

			ret = {
				'page_desc'   : out_soup.prettify(),
				'page_title'  : post_title.get_text().strip(),
				'post_time'   : parsed_post_time,
				'post_tags'   : [],  # I don't think there are tags on Kemono?
				'post_embeds' : external_embeds,
			}


			# Youtube etc are embedded as iframes.
			for ifr in soup.find_all("iframe", src=True):
				ret['post_embeds'].append(ifr['src'])
		except KeyboardInterrupt:
			raise

		# except:
		# 	import IPython
		# 	IPython.embed()

		files = list(set(files))

		if len(files):
			self.log.info("Found %s images/attachments on post.", len(files))
		else:
			self.log.warning("No images/attachments on post %s!", post_url)


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
		except SystemExit:
			raise
		except KeyboardInterrupt:
			raise


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

		except SystemExit:
			raise
		except KeyboardInterrupt:
			raise

		except:
			self.log.error("Unknown error in page retrieval!")
			self.log.error("PostID = '%s'", post_url)
			self.log.error(traceback.format_exc())


		return extends

	def _load_discord_channel(self, channel_obj, local_aid, artist_undecoded, kemono_service, kemono_aid):

		offset = 0
		step = 150

		total_items = []

		while 1:
			channel_url = "https://kemono.su/api/v1/discord/channel/{channel}?o={offset}".format(
					channel = channel_obj['id'],
					offset  = offset,
				)

			page_items = self.wg.getJson(channel_url)



			if not page_items:
				break

			for item in page_items:
				item['referring_url'] = channel_url
				item['channel_name']  = channel_obj['name']
				total_items.append((item['id'], item))


			offset += step


		return total_items

	def _load_discord_pages(self, local_aid, artist_undecoded, kemono_service, kemono_aid):

		root_discord_url = "https://kemono.su/api/v1/discord/channel/lookup/{aid}".format(aid=kemono_aid)


		channel_listing = self.wg.getJson(root_discord_url)
		have = []

		for channel_obj in channel_listing:
			new_items = self._load_discord_channel(channel_obj, local_aid, artist_undecoded, kemono_service, kemono_aid)
			have.extend(new_items)

		return have

	def _load_discord(self, artist_undecoded, kemono_service, kemono_aid, artist_decoded):
		local_aid = self._artist_name_to_rid(artist_undecoded)

		item_key = "{}-{}-{}-fetchtime".format("kemono", "content_list_fetch", local_aid)
		have = self.db.get_from_db_key_value_store(item_key)

		# If we've fetched it in the last 2 weeks, don't retry it.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*7*2):
			pass

		else:
			oldArt = self._getPreviouslyRetreived(artist_undecoded)
			artPages = self._load_discord_pages(local_aid,artist_undecoded, kemono_service, kemono_aid)
			self.log.info("Total gallery items %s", len(artPages))


			new = 0
			post_hashes = []
			with self.db.context_sess() as sess:
				self.log.info("Upserting files")
				for discord_post_id, item_struct in tqdm.tqdm(artPages):
					item = "{}:{}:{}:{}".format(
							"kemono",
							"discord",
							artist_decoded['name'],
							discord_post_id,
						)
					post_hashes.append(item)

					new += self._upsert_if_new(sess, local_aid, item, content_structured=item_struct)

			self.log.info("%s new art pages, %s total", new, len(artPages))

			art_set = set(post_hashes)

			newArt = art_set - oldArt
			self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})

		return self._getNewToRetreive(aid=local_aid)

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


			if kemono_service == 'discord':
				newArt = self._load_discord(artist_undecoded, kemono_service, kemono_aid, artist_decoded)
			else:
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

		except SystemExit:
			raise
		except KeyboardInterrupt:
			raise

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
		creators_api_endpoint = "https://kemono.su/api/v1/creators"

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



		item_key = "kemono-artist-fetchtime"
		have = self.db.get_from_db_key_value_store(item_key)

		# If we've fetched it in the last 2 days, don't retry it.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*2):
			return super().getNameList()




		artist_lut = self.get_artist_listing()

		# try:
		# 	artist_lut = self.get_artist_listing()
		# except Exception as e:
		# 	import IPython
		# 	IPython.embed()

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


		self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})

		return super().getNameList()



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def load_art_pages(self, local_aid, artist_undecoded, kemono_service, kemono_aid):
		now = datetime.datetime.utcnow().replace(tzinfo = pytz.utc).replace(microsecond=0)


		art_listing_url = "https://kemono.su/{service}/user/{aid}?o={offset}"


		post_articles = set()

		for offset in range(0, 99999999, 50):
			soup = self.wg.getSoup(art_listing_url.format(service=kemono_service, aid=kemono_aid, offset=offset))

			articles = soup.find_all("article")

			if not articles:
				break


			this_page = set()

			for article in articles:

				if not article.a:
					import IPython
					IPython.embed()

				post_url = urllib.parse.urljoin(art_listing_url, article.a['href'])

				this_page.add(post_url)

			if this_page.issubset(post_articles):
				break

			post_articles = post_articles | this_page

			self.log.info("iterating over listing of posts. Found %s so far.", len(post_articles))


			self.random_sleep(2,4,15, include_long=False)

		return post_articles


	def get_from_artist_names(self, artist_list, ctrlNamespace, ignore_other=False):

		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")

		is_another_active = self.getRunningStatus(self.pluginShortName)

		if is_another_active and not ignore_other:
			self.log.error("Another instance of the %s scraper is running.", self.pluginShortName)
			self.log.error("Not starting")
			return

		try:
			self.updateRunningStatus(self.pluginShortName, True)
			startTime = datetime.datetime.now()
			self.updateLastRunStartTime(self.pluginShortName, startTime)

			nameList = self.getNameList()

			nameList = [tmp for tmp in nameList if any([tgt.lower() in str(tmp).lower() for tgt in artist_list])
			]

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

			self.log.info("Queueing %s artists to fetch", len(nameList))

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
