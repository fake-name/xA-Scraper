
import os
import io
import os.path
import traceback
import re
import pprint
import time
import json
import urllib.request
import urllib.parse
import random
import pprint

import requests
import dateparser
import bs4
import pixivpy3
import pixivpy3.utils
import ChromeController

import flags
from settings import settings
import xascraper.modules.scraper_base
from xascraper.modules import exceptions


def convert_pixiv_object(pixiv_object):
	'''
	PixivPy has an obnoxious custom dict type they use. That'd be fine, if it
	didn't break sqlalchemy dict fields.

	Anyways, recursively convert those.
	'''
	if isinstance(pixiv_object, (pixivpy3.utils.JsonDict, dict)):
		return {
			key : convert_pixiv_object(value) for key, value in pixiv_object.items()
		}

	if isinstance(pixiv_object, (list, tuple)):
		return [convert_pixiv_object(value) for value in pixiv_object]

	return pixiv_object



#####################################################

import base64
import hashlib
import secrets
import urllib.parse

# Latest app version can be found using GET /v1/application-info/android
USER_AGENT     = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
REDIRECT_URI   = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL      = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID      = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET  = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"

'''
cr.execute_javascript_statement("""
document.querySelectorAll('button').forEach( (e)=>{
    if (e.textContent.includes('Continue using this account')) {
        e.click();
    }
})
""")

cr.execute_javascript_statement("""
document.querySelectorAll('button')
""")


cr.execute_javascript_statement("""
document.querySelectorAll('button').forEach( (e)=>{})
""")
'''

def s256(data):
	"""S256 transformation method."""

	return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")


def oauth_pkce(transform):
	"""Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

	code_verifier = secrets.token_urlsafe(32)
	code_challenge = transform(code_verifier.encode("ascii"))

	return code_verifier, code_challenge


def extract_auth_token_response(response):
	data = response.json()

	try:
		access_token = data["access_token"]
		refresh_token = data["refresh_token"]

		print("access_token:", access_token)
		print("refresh_token:", refresh_token)
		print("expires_in:", data.get("expires_in", 0))

		return access_token, refresh_token

	except KeyError:
		print("error:")
		pprint.pprint(data)

		return None, None


#####################################################


class GetPX(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "px"
	pluginName     = "PxGet"

	urlBase         = "http://www.pixiv.net/"
	ovwMode         = "Check Files"

	numThreads      = 1

	extra_wg_params = {"chromium_headless" : False}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.aapi = pixivpy3.AppPixivAPI()
		# self.papi = pixivpy3.PixivAPI()

		saved_auth = self.get_param_cache()

		if saved_auth:
			self.log.info("Using cached auth")

			self.aapi.set_auth(access_token=saved_auth['a_access_token'], refresh_token=saved_auth['a_refresh_token'])


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		if not self.aapi.access_token:
			self.log.info("No auth present. Need to log in!")
			return False, "Do not have Pixiv Cookies"

		try:

			data = self.aapi.illust_follow(restrict="private")

			if "error" in data:

				try:
					self.log.info("Not logged in: %s", data['error']['message'])
				except KeyError:
					self.log.error("No error message in response? Response: %s", data)


				return False, "Not logged in!"


			return True, "Have Pixiv Auth Token:\n	-> %s" % (self.aapi.access_token)

		except Exception as e:
			self.log.error("Failure when checking cookie: %s", e)
			import IPython
			IPython.embed()

			return False, "Do not have Pixiv Cookies"





	def getCookie(self):
		self.log.info("Pixiv Getting cookie")

		sent_reqs = []

		auth_keys = {}

		def content_handler(container, req_url, response_body):
			print("Content:", req_url)



		def install_msg_handler(ctx, message):
			if 'method' in message and message['method'] == "Network.requestWillBeSent":
				sent_reqs.append(message)

				if "params" not in message:
					return

				if "documentURL" not in message['params']:
					return

				if not message['params']['documentURL'].startswith("pixiv"):
					return

				auth_url = message['params']['documentURL']


				if not auth_url:
					self.log.error("Authentication failed, no oauth code found!")
					return False, "Login Failed"

				qs = urllib.parse.urlparse(auth_url).query
				parsed = urllib.parse.parse_qs(qs)

				if 'code' not in parsed:
					self.log.error("Oauth code missing from URL: %s!", auth_url)
					return False, "Login Failed"

				if not parsed['code']:
					self.log.error("Oauth code field empty from URL: %s!", auth_url)
					return False, "Login Failed"

				code = parsed['code'][0]

				self.log.info("Login auth code: %s", code)




				response = requests.post(
					AUTH_TOKEN_URL,
					data={
						"client_id": CLIENT_ID,
						"client_secret": CLIENT_SECRET,
						"code": code,
						"code_verifier": code_verifier,
						"grant_type": "authorization_code",
						"include_policy": "true",
						"redirect_uri": REDIRECT_URI,
					},
					headers={"User-Agent": USER_AGENT},
				)

				access_token, refresh_token = extract_auth_token_response(response)

				auth_keys['access_token']  = access_token
				auth_keys['refresh_token'] = refresh_token




		with ChromeController.chrome_context.ChromeContext(binary='google-chrome', headless=False) as cr:

			# cr.clear_cookies()

			self.log.info("Installing listener")
			cr.install_message_handler(install_msg_handler)

			code_verifier, code_challenge = oauth_pkce(s256)
			login_params = {
				"code_challenge": code_challenge,
				"code_challenge_method": "S256",
				"client": "pixiv-android",
			}

			login_url = f"{LOGIN_URL}?{urllib.parse.urlencode(login_params)}"
			cr.blocking_navigate(login_url)

			time.sleep(4)
			self.log.info("Clicking continue button (if present)")
			cr.execute_javascript_statement("""
				document.querySelectorAll('button').forEach( (e)=>{
				    if (e.textContent.includes('Continue using this account')) {
				        e.click();
				    }
				});
				""")


			current_url = cr.get_current_url()
			self.log.info("Current URL: %s", current_url)

			cr.execute_javascript_function("document.querySelector(\"input[type='text']\").focus()")
			for char in settings[self.pluginShortName]['username']:
				cr.Input_dispatchKeyEvent(type='char', code="Backspace")
				cr.Input_dispatchKeyEvent(type='char', code="Backspace")
			for char in settings[self.pluginShortName]['username']:
				cr.Input_dispatchKeyEvent(type='char', text=char)

			cr.execute_javascript_statement("document.querySelector(\"input[type='password']\").focus()")
			for char in settings[self.pluginShortName]['password']:
				cr.Input_dispatchKeyEvent(type='char', code="Backspace")
				cr.Input_dispatchKeyEvent(type='char', code="Backspace")
			for char in settings[self.pluginShortName]['password']:
				cr.Input_dispatchKeyEvent(type='char', text=char)

			time.sleep(4)
			self.log.info("Clicking login.")


			cr.execute_javascript_statement("""
				document.querySelectorAll('button').forEach( (e)=>{
				    if (e.textContent.includes('Log In')) {
				        console.log(e);
				        console.log(e.textContent);
				        e.click();
				    }
				})
				""")

			time.sleep(4)

			# process events as a result of the click.
			# We wait for 90 seconds because the login can involve solving a captcha and other messyness
			LOGIN_DELAY = 90
			starttime = time.time()

			while 1:
				if (starttime + LOGIN_DELAY) < time.time():
					break

				if  'access_token' in auth_keys:
					break

				resp = cr.execute_javascript_statement("""
					document.querySelectorAll('button').forEach( (e)=>{
					    if (e.textContent.includes('Continue using this account')) {
					        console.log(e);
					        console.log(e.textContent);
					        e.click();
					    }
					    if (e.textContent.includes('Log In')) {
					        console.log(e);
					        console.log(e.textContent);
					        e.click();
					    }
					})
					""")

				self.log.info("Click response: '%s'", resp)

				try:
					cr.handle_page_location_changed()
				except Exception:
					# page_location_changed can be broken by redurects to external app handlers
					pass

				remaining = (starttime + LOGIN_DELAY) - time.time()

				self.log.info("Waiting %s more seconds.", remaining)


			self.log.info("Auth info at exit: %s", auth_keys)


			if  'access_token' not in auth_keys or 'refresh_token' not in auth_keys:
				return False, None


			self.aapi.set_auth(access_token=auth_keys['access_token'], refresh_token=auth_keys['refresh_token'])

			ok = self.aapi.trending_tags_illust()
			assert "error" not in ok

		if self.aapi.access_token and self.aapi.access_token:

			config = {
				'a_access_token'  : self.aapi.access_token,
				'a_refresh_token' : self.aapi.refresh_token,
				}
			self.set_param_cache(config)

			return True, "Logged In"

		else:
			return False, "Login Failed"

	def checkLogin(self):

		logged_in, message = self.checkCookie()
		if not logged_in:
			logged_in, message = self.getCookie()
			if not logged_in:
				raise RuntimeError("Could not log in?")

		return logged_in, message

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def __papi_download(self, url, referer='https://app-api.pixiv.net/'):
		"""Download image to file (use 6.0 app-api)"""
		response = self.papi.requests_call('GET', url, headers={ 'Referer': referer }, stream=True)
		return response.raw.read()


	def _extractTitleDescription(self, meta):
		itemTitle   = meta['title']
		itemCaption = meta['caption']
		postTime    = dateparser.parse(meta['create_date']).replace(tzinfo=None)

		postTags    = [tmp['name'] for tmp in meta['tags'] if tmp['name']] + \
			[tmp['translated_name'] for tmp in meta['tags'] if 'translated_name' in tmp and tmp['translated_name']] + \
			["tool " + tmp for tmp in meta['tools'] if tmp]
		postTags.append("sanity level %s" % meta['sanity_level'])
		return itemTitle, itemCaption, postTime, postTags

	def _get_best_ugoira_from_set(self, imgset):
		if 'ugoira1920x1080' in imgset:
			return imgset['ugoira1920x1080']
		if 'original' in imgset:
			return imgset['original']
		if 'large' in imgset:
			self.log.warning("No original image (found large)?")
			return imgset['large']
		if 'medium' in imgset:
			self.log.warning("No large image (found medium)?")
			return imgset['medium']
		if 'small' in imgset:
			self.log.warning("No large image (found small)?")
			return imgset['small']
		if 'ugoira600x600' in imgset:
			self.log.warning("No large image (found ugoira600x600)?")
			return imgset['ugoira600x600']
		raise RuntimeError("No ugoira1920x1080 or ugoira600x600 images!")

	def _get_best_image_from_set(self, imgset):
		if 'original_image_url' in imgset:
			return imgset['original_image_url']
		if 'original' in imgset:
			return imgset['original']
		if 'large' in imgset:
			self.log.warning("No original image (found large)?")
			return imgset['large']
		if 'medium' in imgset:
			self.log.warning("No large image (found medium)?")
			return imgset['medium']
		if 'small' in imgset:
			self.log.warning("No large image (found small)?")
			return imgset['small']

		raise RuntimeError("No large, medium or small images!")


	def _getAnimation(self, dlPathBase, item_meta):
		# TODO: Unpack ugoira unto a apng/gif (or at least a set of files)

		imgurl   = self._get_best_ugoira_from_set(item_meta['ugoira_metadata']['zip_urls'])

		buf = io.BytesIO()
		assert self.aapi.download(imgurl, fname=buf)
		fcont = buf.getvalue()

		regx4 = re.compile(r"http://.+/")				# FileName RE
		fname = regx4.sub("" , imgurl)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.
		fname = fname.rsplit("/")[-1]

		self.log.info("			Filename = %s", fname)
		self.log.info("			FileURL = %s", imgurl)

		file_path = os.path.join(dlPathBase, fname)
		saved_to = self.save_file(file_path, fcont)

		return [saved_to]


	def _extract_images(self, item_meta, dlPathBase):

		images = []

		regx4 = re.compile(r"http://.+/")				# FileName RE

		if 'meta_single_page' in item_meta and item_meta['meta_single_page']:

			imgurl   = self._get_best_image_from_set(item_meta['meta_single_page'])


			buf = io.BytesIO()
			assert self.aapi.download(imgurl, fname=buf)
			fcont = buf.getvalue()


			fname = regx4.sub("" , imgurl)
			fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.
			fname = fname.rsplit("/")[-1]

			self.log.info("			Filename = %s", fname)
			self.log.info("			FileURL = %s",  imgurl)

			file_path = os.path.join(dlPathBase, fname)
			saved_to = self.save_file(file_path, fcont)

			images.append(saved_to)



		index = 1
		for imagedat in item_meta['meta_pages']:
			imgurl = self._get_best_image_from_set(imagedat['image_urls'])

			buf = io.BytesIO()
			assert self.aapi.download(imgurl, fname=buf)
			fcont = buf.getvalue()

			fname = regx4.sub("" , imgurl)
			fname = fname.rsplit("?")[0]
			fname = fname.rsplit("/")[-1]
			fname, ext = os.path.splitext(fname)
			fname = "%s - %04d%s" % (fname, index, ext)
			index += 1

			self.log.info("			Filename = %s", fname)
			self.log.info("			FileURL = %s", imgurl)
			file_path = os.path.join(dlPathBase, fname)
			saved_to = self.save_file(file_path, fcont)

			images.append(saved_to)

		return images



	def _getArtPage(self, dlPathBase, item_params, artistName):
		'''
		Pixiv does a whole lot of referrer sniffing. They block images, and do page redirects if you don't submit the correct referrer.
		Also, I *think* they will block flooding, so that's the reason for the delays everywhere.
		'''

		params = json.loads(item_params)
		item_type = params['type']
		item_id   = params['id']

		try:

			self.log.info("Fetching details for post: https://www.pixiv.net/en/artworks/%s", item_id)

			illust_deets = self.aapi.illust_detail(item_id)

			if 'error' in illust_deets:
				try:

					if 'Error occurred at the OAuth process. Please check your Access Token to fix this. Error Message: invalid_grant' in illust_deets['error']['message']:
						raise exceptions.NotLoggedInException("Login expired!")

					self.log.info("Error fetching item: %s", illust_deets['error']['message'])
					return self.build_page_ret(status="Failed", pageTitle="Failed: %s" % illust_deets['error']['message'], fqDlPath=None)

				except KeyError as e:
					return self.build_page_ret(status="Failed", pageTitle="Failed: %s" % e, fqDlPath=None)

			if not 'illust' in illust_deets:
				print("No illust field in illust_deets?")
				print(illust_deets)

				import IPython
				IPython.embed()


			illust    = illust_deets['illust']
			item_type = illust['type']

			itemTitle, itemCaption, postTime, postTags = self._extractTitleDescription(illust)

			self.log.info("			postTime = %s", postTime)
			self.log.info("			postTags = %s", postTags)


			if item_type == 'ugoira':
				self.log.info("Saving animation")
				ugoira_meta = self.aapi.ugoira_metadata(item_id)

				if 'error' in ugoira_meta and ugoira_meta['error']['user_message'] == 'Artist has made their work private.':
					return self.build_page_ret(status="Failed", pageTitle="Artist has made their work private: %s" % ugoira_meta, fqDlPath=None)


				images = self._getAnimation(dlPathBase, ugoira_meta)

				return self.build_page_ret(status="Succeeded",
						fqDlPath           = images,
						pageDesc           = itemCaption,
						pageTitle          = itemTitle,
						postTags           = postTags,
						postTime           = postTime,
						content_structured = convert_pixiv_object(ugoira_meta),
					)



			elif item_type in ['manga', 'illust']:

				images = self._extract_images(illust, dlPathBase)

				self.random_sleep(1,5,15, include_long=False)
				return self.build_page_ret(status="Succeeded",
						fqDlPath  = images,
						pageDesc  = itemCaption,
						pageTitle = itemTitle,
						postTags  = postTags,
						postTime  = postTime
					)


			else:
				print("Item that isn't ugoira or image! This needs to be handled!")
				import IPython
				IPython.embed()


		except pixivpy3.PixivError as err:
			raise exceptions.RetryException("Error: '%s'" % err)

		raise RuntimeError("Unknown item type: '%s' for artist:item_id -> %s -> %s" % (item_type, artistName, item_id))

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _check_limited(self, item_content):


		if not item_content:

			print("No item content?")

			import IPython
			IPython.embed()

		if "error" in item_content and not item_content["error"]:

			print("Empty error section!")

			import IPython
			IPython.embed()

		# There is a "message" field, and a "user_message" field.
		# Yeeeaaahhhhh
		if "error" in item_content and 'message' in item_content["error"] and item_content["error"]['message'] == 'Rate Limit':
			self.random_sleep(10,20,120, include_long=False)
			raise exceptions.RetryException("Rate Limited.")

		if "error" in item_content and 'message' in item_content["error"] and item_content["error"]['message'] == 'Error occurred at the OAuth process. Please check your Access Token to fix this. Error Message: invalid_grant':
			self.random_sleep(1,2,5, include_long=False)
			raise exceptions.NotLoggedInException("Need to reauthenticate!")

		if "error" in item_content and 'user_message' in item_content["error"] and item_content["error"]['user_message'] == 'The creator has limited who can view this content':
			self.random_sleep(1,2,5, include_long=False)
			raise exceptions.AccountDisabledException("Account is locked for viewing!")

		if "error" in item_content and 'user_message' in item_content["error"] and item_content["error"]['user_message'] == 'Page not found':
			self.random_sleep(1,2,5, include_long=False)
			raise exceptions.AccountDisabledException("Account has been removed!")

		# I think this is caused by accounts that have been deleted.
		if "error" in item_content and 'user_message' in item_content["error"] and item_content["error"]['user_message'] == 'Your access is currently restricted.':
			self.random_sleep(1,2,5, include_long=False)
			raise exceptions.AccountDisabledException("Access is restricted?")


		if "error" in item_content and 'user_message' in item_content["error"] and item_content["error"]['user_message'] == 'Error occurred at the OAuth process. Please check your Access Token to fix this. Error Message: invalid_grant':
			self.random_sleep(1,2,5, include_long=False)
			raise exceptions.NotLoggedInException("Need to reauthenticate!")


		if "error" in item_content and item_content["error"]:

			print("Error without a message?")

			print("'item_content' : ")
			print(item_content)

			import IPython
			IPython.embed()



	def __getTotalArtCount(self, aid):


		user_details = self.aapi.user_detail(aid)

		if not user_details:
			raise exceptions.FetchFailedException("No details for artist: %s" % (user_details, ))

		self._check_limited(user_details)

		if not "profile" in user_details:
			import IPython
			IPython.embed()


		return user_details["profile"]['total_illusts'] + user_details["profile"]['total_manga'] + user_details["profile"]['total_novels']

	def _getTotalArtCount(self, aid):
		try:
			return self.__getTotalArtCount(aid)
		except exceptions.NotLoggedInException as err:
			self.log.warning("failed to get art count (%s). Checking login status.", err)
			_, status = self.checkLogin()
			self.log.info("Login status: %s", status)
			return self.__getTotalArtCount(aid)




	def _getGalleries(self, artist):
		aid = int(artist)

		artlinks = set()


		try:
			art_types = ['illust', 'manga']

			for art_type in art_types:


				qs = {
					'user_id' : aid,
					'type'    : art_type,
				}

				while qs:

					self.log.info("Fetching items: %s", qs)
					json_result = self.aapi.user_illusts(**qs)
					if not json_result:

						print("No item content?")

						import IPython
						IPython.embed()

					if "error" in json_result and not json_result["error"]:

						print("Empty error section!")

						import IPython
						IPython.embed()


					self._check_limited(json_result)

					qs = self.aapi.parse_qs(json_result.next_url)

					artlinks.update(
							json.dumps({
								"id":   tmp["id"],

								# This is gross, but I've been calling the "illust" type "illustration" in the db.
								"type": "illustration" if tmp["type"] == "illust" else tmp["type"],
							}, sort_keys=True) for tmp in json_result.illusts
						)

					self.random_sleep(1,2,5, include_long=False)


			self.log.info("Found %s links", len(artlinks))

		except KeyError:
			self.log.error("Error while attempting to get gallery listing!")
			for line in traceback.format_exc().split("\n"):
				self.log.error(line)

			self.log.error("Aborting run!")

			raise exceptions.RetryException("What?")

		return artlinks


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):
		self.checkLogin()

		item_key = "px:last_artist_list_update"

		have = self.db.get_from_db_key_value_store(item_key)

		# If we've fetched it in the last 2 days, don't grab the item again.
		if have and 'last_fetch' in have and have['last_fetch'] and have['last_fetch'] > (time.time() - 60*60*24*2):
			self.log.info("Fetched artist list within the last two days. Skipping.")


		else:
			self.log.info("Getting list of favourite artists.")

			resultlist = set()

			modes = ['public', 'private']

			for mode in modes:
				self.log.info("Fetching %s follows", mode)

				qs = {"restrict" : mode}

				while qs:

					json_result = self.aapi.illust_follow(**qs)

					new_ids = [entry['user']['id'] for entry in json_result['illusts']]
					resultlist.update(new_ids)

					qs = self.aapi.parse_qs(json_result.next_url)
					self.log.info("Found %s names so far (%s on page)", len(resultlist), len(new_ids))

					self.random_sleep(1,2,5, include_long=False)

			assert not any('-' in str(tmp) for tmp in resultlist)

			self.log.info("Found %d Names", len(resultlist))

			self.log.info("Inserting IDs into DB")
			# Push the pixiv name list into the DB
			with self.db.context_sess() as sess:
				for name in resultlist:

					# Name entries are strings in the DB.
					# Yeeaaaaaaah
					name = str(name)

					res = sess.query(self.db.ScrapeTargets.id)             \
						.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
						.filter(self.db.ScrapeTargets.artist_name == name)              \
						.scalar()
					if not res:
						self.log.info("Need to insert name: %s", name)
						sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name))
						sess.commit()

			self.db.set_in_db_key_value_store(item_key, {'last_fetch' : time.time()})

		ret = super().getNameList()




		return ret




