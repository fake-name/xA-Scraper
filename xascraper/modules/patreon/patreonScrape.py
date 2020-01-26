import os
import os.path
import traceback
import datetime
import pytz
import dateutil.parser
import bs4
import WebRequest
import urllib.parse
import json
import time
import pprint
from settings import settings

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

class GetPatreon(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "pat"

	pluginName = "PatreonGet"

	urlBase = None

	ovwMode = "Check Files"

	numThreads = 1

	custom_ua = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0'),
				 ('Accept-Language', 'en-US'),
				 ('Accept', 'application/xml, application/xhtml+xml, text/html;q=0.9,  text/plain;q=0.8, image/png, */*;q=0.5'),
				 ('Accept-Encoding', 'deflate,sdch,gzip')]

	# Stubbed functions
	_getGalleries = None
	_getTotalArtCount = None

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# This is.... kind of horrible.
		self.wg.errorOutCount = 1



	def checkCookie(self):
		print("Checking login!")
		try:
			current = self.get_api_json("/current_user", retries=1)
		except Exception:
			print("Not logged in!")
			current = False

		if not current or current['data']['id'] == 0:
			return False, "Not logged in"
		else:
			return True, "Autheticated OK"

	def handle_recaptcha(self, soup, containing_page, referrer_url):
		self.log.warning("Hit recaptcha. Attempting to solve.")

		key = settings['captcha']['anti-captcha']['api_key']
		solver = WebRequest.AntiCaptchaSolver(api_key=key, wg=self.wg)
		form = soup.find("form", id="challenge-form")

		args = {}
		for input_tag in form.find_all('input'):
			if input_tag.get('name'):
				args[input_tag['name']] = input_tag['value']


		captcha_key = form.script['data-sitekey']

		self.log.info("Captcha key: %s with input values: %s", captcha_key, args)

		recaptcha_response = solver.solve_recaptcha(google_key=captcha_key, page_url=containing_page)

		self.log.info("Captcha solved with response: %s", recaptcha_response)
		args['g-recaptcha-response'] = recaptcha_response

		solved_soup = self.wg.getpage(
				urllib.parse.urljoin(containing_page, form['action']),
				postData    = args,
				addlHeaders = {'Referer': referrer_url},
			)

		return solved_soup



	def getCookie(self):
		if self.checkCookie()[0]:
			return True, "Already logged in"

		self.log.info("Trying to avoid rate limiting!")
		time.sleep(5)

		self.log.info("Not logged in. Doing login.")

		home  = "https://www.patreon.com/home"
		login = "https://www.patreon.com/login"
		soup = self.wg.getSoup(home)

		# These won't work for the particular recaptcha flavor patreon uses. Sigh.
		if soup.find_all("div", class_="g-recaptcha"):
			soup = WebRequest.as_soup(self.handle_recaptcha(soup, home, login))

		if soup.find_all("div", class_="g-recaptcha"):
			self.log.error("Failed after attempting to solve recaptcha!")
			raise exceptions.NotLoggedInException("Login failed due to recaptcha!")

		login_data = {
			'type' : 'user',
			'relationships' : {},
			'attributes' : {
					"email"    : settings[self.pluginShortName]['username'],
					"password" : settings[self.pluginShortName]['password'],
				}
		}
		try:
			current = self.get_api_json("/login?json-api-version=1.0", postData=login_data, retries=1)
			self.log.info("Login results: %s", current)
		finally:
			self.log.info("Flushing cookies unconditionally.")
			self.wg.saveCookies()

		return self.checkCookie()

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Internal utilities stuff
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	def __cf_check(self, url, *args, **kwargs):
		try:
			content = self.wg.getpage(url, *args, **kwargs)
		except WebRequest.FetchFailureError as e:
			if e.err_code == 403 and b"Attention Required! | Cloudflare" in e.err_content:
				e_soup = WebRequest.as_soup(e.err_content)
				self.handle_recaptcha(e_soup, url, "https://www.patreon.com/home")
				print()
				print(e.err_content)
				print()
				print(e.err_reason)
				print()
				return self.wg.getpage(url, *args, **kwargs)
			raise
		return content

	def get_api_json(self, endpoint, postData = None, retries=1):
		if postData:
			postData = {"data" : postData}
			postData = json.dumps(postData, sort_keys=True)

		assert endpoint.startswith("/"), "Endpoint isn't a relative path! Passed: '%s'" % endpoint

		try:
			content = self.__cf_check(
					"https://www.patreon.com/api{endpoint}".format(endpoint=endpoint),
					addlHeaders={
						"Accept"          : "application/json",
						"Origin"          : "https://www.patreon.com",
						"Host"            : "www.patreon.com",
						"Content-Type"    : "application/json",
						"Accept-Encoding" : "gzip, deflate",
						"Authority"       : "www.patreon.com",
						"Scheme"          : "https",
						# "Referer"         : "https://www.patreon.com/login",
						# "Pragma"          : "no-cache",
						# "Cache-Control"   : "no-cache",
						},
					postData      = postData,
					retryQuantity = retries
				)
		except Exception as e:
			traceback.print_exc()
			raise exceptions.UnrecoverableFailureException("Wat?")


		if content is None:
			self.log.error("Couldn't login! Please check username and password!")
			raise LoginFailure("Failed to login. Please check your username and password are correct!")

		content = content.decode("utf-8")
		vals = json.loads(content)
		return vals


	def current_user_info(self):
		current = self.get_api_json("/current_user?include=pledges&include=follows")
		return current


	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_save_dir(self, aname):

		dirp = self.getDownloadPath(self.dlBasePath, aname)
		if not os.path.exists(dirp):
			os.makedirs(dirp)
		return dirp

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
			content = self.wg.getpage(furl, addlHeaders={"Referer" : "https://www.patreon.com/home"})
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
			content = self.wg.getpage(url, addlHeaders={"Referer" : "https://www.patreon.com/home"})
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
			content = self.wg.getpage(url, addlHeaders={"Referer" : "https://www.patreon.com/home"})
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

	def _get_art_post(self, postId, artistName):
		post = self.get_api_json("/posts/{pid}".format(pid=postId) +
			"?include=media"
			)

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
		pprint.pprint(post_content)

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


		ctnt_soup = bs4.BeautifulSoup(post_info['content'], 'lxml')
		for img in ctnt_soup.find_all("img", src=True):
			furl = img['src']
			fparsed = urllib.parse.urlparse(furl)
			fname = fparsed.path.split("/")[-1]
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
			return self._get_art_post(postid, artistName)
		else:
			self.log.error("Unknown post type: '%s'", item_type)
			raise RuntimeError("Wat?")

	def _load_art(self, patreon_aid, artist_raw):
		aid = self._artist_name_to_rid(artist_raw)

		artPages = self.get_campaign_posts(patreon_aid)

		self.log.info("Total gallery items %s", len(artPages))

		new = 0
		with self.db.context_sess() as sess:
			for item in artPages:
				item_json = json.dumps(item, sort_keys=True)
				new += self._upsert_if_new(sess, aid, item_json)

		self.log.info("%s new art pages, %s total", new, len(artPages))

		oldArt = self._getPreviouslyRetreived(artist_raw)
		newArt = artPages - oldArt
		self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

		new_raw = self._getNewToRetreive(aid=aid)

		return [json.loads(tmp) for tmp in new_raw]

	def getArtist(self, artist_undecoded, ctrlNamespace):
		artist_decoded = json.loads(artist_undecoded)
		patreon_aid, artist_meta = artist_decoded
		artist_name, artist_meta = artist_meta

		if ctrlNamespace.run is False:
			# self.log.warning("Exiting early from %s due to run flag being unset", artist_undecoded)
			return True

		try:
			self.log.info("GetArtist - %s -> %s", artist_name, artist_undecoded)
			self.setupDir(artist_name)

			if 'campaign' in artist_meta and artist_meta['campaign']['data']['type'] == 'campaign':
				campaign_id = artist_meta['campaign']['data']['id']

				newArt = self._load_art(patreon_aid, artist_undecoded)
			else:
				newArt = []


			embeds = []


			while len(newArt) > 0:
				postid = newArt.pop()
				postid_s = json.dumps(postid)
				try:
					ret = self._fetch_retrier(postid, artist_name)

					assert isinstance(ret, dict)
					assert 'status'     in ret

					if 'post_embeds' in ret:
						embeds.extend(ret['post_embeds'])

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
									artist=artist_undecoded,
									state='complete',
									release_meta=json.dumps(postid),
									fqDlPath=item,
									pageDesc=ret['page_desc'],
									pageTitle=ret['page_title'],
									seqNum=seq,
									addTime=ret['post_time'],
									postTags=ret['post_tags'],
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
		artist_lut = {item['id'] : (item['attributes']['full_name'], item['relationships']) for item in general_meta['included'] if item['type'] == 'user'}

		return artist_lut

	def getNameList(self):
		self.getCookie()

		self.log.info("Getting list of favourite artists.")

		artist_lut = self.get_artist_lut()

		self.log.info("Found %d Names", len(artist_lut))
		for key, value in artist_lut.items():
			print((key, value))

		resultList = [json.dumps((key, value), sort_keys=True) for key, value in artist_lut.items()]
		# Push the pixiv name list into the DB
		with self.db.context_sess() as sess:
			for name in resultList:
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()
				if not res:
					self.log.info("Need to insert name: %s", name)
					sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name))
					sess.commit()

		return super().getNameList()



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_campaign_posts(self, patreon_aid, count=10):
		now = datetime.datetime.utcnow().replace(tzinfo = pytz.utc).replace(microsecond=0)

		postids = set()
		types = ['posts', 'poll']
		while True:
			current = self.get_api_json("/stream?" +
				"include=recent_comments.commenter%2Crecent_comments.parent%2Crecent_comments.post%2Crecent_comments.first_reply.commenter%2Crecent_comments.first_reply.parent%2Crecent_comments.first_reply.post" +
				"&fields[post]=change_visibility_at%2Ccomment_count%2Ccontent%2Ccurrent_user_can_delete%2Ccurrent_user_can_view%2Ccurrent_user_has_liked%2Cearly_access_min_cents%2Cembed%2Cimage%2Cis_paid%2Clike_count%2Cmin_cents_pledged_to_view%2Cpost_file%2Cpublished_at%2Cpatron_count%2Cpatreon_url%2Cpost_type%2Cpledge_url%2Cthumbnail_url%2Ctitle%2Cupgrade_url%2Curl" +
				"&fields[user]=image_url%2Cfull_name%2Curl" +
				"&fields[campaign]=earnings_visibility" +
				"&page[cursor]={now}".format(now=str(now.isoformat())) +
				"&filter[is_by_creator]=true" +
				"&filter[is_following]=false" +
				"&filter[creator_id]={patreon_aid}".format(patreon_aid=patreon_aid) +
				"&filter[contains_exclusive_posts]=true" +
				"&json-api-use-default-includes=false" +
				"&json-api-version=1.0" +
				"&fields[comment]=body%2Ccreated%2Cdeleted_at%2Cis_by_patron%2Cis_by_creator%2Cvote_sum%2Ccurrent_user_vote%2Creply_count" +
				"&fields[post]=comment_count" +
				"&fields[user]=image_url%2Cfull_name%2Curl" +
				""
				)

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

					if release['type'] != "post":
						self.log.warning("Non post release!")
				else:
					self.log.warning("Unknown type!")
					for line in pprint.pformat(release).split("\n"):
						self.log.warning(line)


			self.log.info("iterating over listing of campaign posts. Found %s so far, have new: %s.", len(postids), had_post)
			if not had_post:
				break

		return postids



	def run_old(self):
		self.check_login()
		# self.get_pledges()
		self.fetch_all()

