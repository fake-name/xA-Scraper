import os
import os.path
import traceback
import datetime
import time
import pytz
import dateutil.parser
import bs4
import base64
import urllib.parse
import json
import time
import tqdm
import random
import pprint
import requests
import ChromeController
from settings import settings

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

PATREON_LOGIN_PAGE = 'https://www.patreon.com/login'
PATREON_HOME_PAGE  = 'https://www.patreon.com/home'


def maybe_decode(in_obj):
	if in_obj['base64Encoded']:
		return base64.b64decode(in_obj['data'])
	else:
		return in_obj['data']

class GetPatreonBase(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "pat"

	pluginName = "PatreonFeedGet"

	urlBase = None

	ovwMode = "Check Files"

	numThreads = 1

	custom_ua = [('user-agent',      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'),
				 ('accept-language', 'en-US,en;q=0.9'),
				 ('accept',          'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'),
				 ('accept-encoding', 'gzip, deflate, br')]


	custom_ua = []

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

		# proxy = SocksProxy.ProxyLauncher([TwoCaptchaSolver.TWOCAPTCHA_IP])
		recaptcha_params = {
				'provider': 'anticaptcha',
				'api_key': settings["captcha"]["anti-captcha"]['api_key'],

				# 'proxy'       : proxy.get_wan_address(),
				# 'proxytype'   : "SOCKS5",
			}

		# self.req = cloudscraper.CloudScraper(
		# 		recaptcha = recaptcha_params,
		# 	)

		# self.req.headers.update(self.wg.browserHeaders)



	def get_soup(self, url):
		# resp = self.req.get(url)
		# assert 'text/html' in resp.headers.get("content-type", ""), "response isn't text/html, it's %s" % resp.headers.get("content-type")
		# return WebRequest.as_soup(resp.text)

		self.cr.blocking_navigate(url)
		content = self.cr.get_rendered_page_source()

		return WebRequest.as_soup(content)

	def checkCookie(self):
		print("Checking login!")
		try:
			page = self.get_soup(PATREON_HOME_PAGE)
			page_str = str(page)
		except Exception:
			# print("Not logged in!")
			current = False
			traceback.print_exc()


		if settings[self.pluginShortName]['username'] in page_str:
			return True, "Autheticated OK"

		# print("Page str:", page_str)

		with open("page.html", "wb") as fp:
			fp.write(page_str.encode("UTF-8"))

		return False, "Not logged in"


	def handle_recaptcha(self, soup, containing_page, referrer_url):
		raise RuntimeError("Oooold")
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

		return WebRequest.as_soup(solved_soup)



	def handle_hcaptcha(self, soup, containing_page, referrer_url):
		self.log.warning("Hit hcaptcha. Attempting to solve.")

		key = settings['captcha']['anti-captcha']['api_key']
		solver = WebRequest.AntiCaptchaSolver(api_key=key, wg=self.wg)
		form = soup.find("form", id="challenge-form")

		args = {}
		for input_tag in form.find_all('input'):
			if input_tag.get('name'):
				args[input_tag['name']] = input_tag['value']


		captcha_key = form.script['data-sitekey']

		self.log.info("Captcha key: %s with input values: %s", captcha_key, args)

		recaptcha_response = solver.solve_hcaptcha(website_key=captcha_key, page_url=containing_page)

		self.log.info("Captcha solved with response: %s", recaptcha_response)
		args['g-recaptcha-response'] = recaptcha_response


		self.cr.execute_javascript_statement("document.querySelector(\"textarea[name='h-captcha-response']\").value = '{}'".format(recaptcha_response))
		self.cr.execute_javascript_statement("document.querySelector(\"form#challenge-form\").submit()")

		solved_soup = self.cr.get_rendered_page_source()
		ret = WebRequest.as_soup(solved_soup)

		return ret


	def getCookie(self):
		if self.checkCookie()[0]:
			return True, "Already logged in"

		self.log.info("Trying to avoid rate limiting!")
		self.random_sleep(4,5,6)

		self.log.info("Not logged in. Doing login.")


		try:
			soup = self.get_soup(PATREON_LOGIN_PAGE)
		except Exception as e:

			import pdb
			print(e)
			pdb.set_trace()
			print(e)

		# These won't work for the particular recaptcha flavor patreon uses. Sigh.
		if soup.find_all("div", class_="g-recaptcha"):
			soup = self.handle_recaptcha(soup, PATREON_HOME_PAGE, PATREON_LOGIN_PAGE)

		if soup.find_all("div", id="hcaptcha_widget"):
			soup = self.handle_hcaptcha(soup, PATREON_HOME_PAGE, PATREON_LOGIN_PAGE)

		if soup.find_all("div", class_="g-recaptcha"):
			self.log.error("Failed after attempting to solve recaptcha!")
			raise exceptions.NotLoggedInException("Login failed due to recaptcha!")

		if soup.find_all("div", class_="hcaptcha_widget"):
			self.log.error("Failed after attempting to solve recaptcha!")
			raise exceptions.NotLoggedInException("Login failed due to recaptcha!")


		# So patreon uses RavenJS, which does a bunch of really horrible change-watching crap on input
		# fields. I couldn't figure out how to properly fire the on-change events, so let's just
		# use the debug-protocol interface to type our login info in manually.
		self.cr.execute_javascript_function("document.querySelector(\"input[type='email']\").focus()")
		for char in settings[self.pluginShortName]['username']:
			self.cr.Input_dispatchKeyEvent(type='char', text=char)
		self.cr.execute_javascript_statement("document.querySelector(\"input[type='password']\").focus()")
		for char in settings[self.pluginShortName]['password']:
			self.cr.Input_dispatchKeyEvent(type='char', text=char)

		self.cr.execute_javascript_statement("document.querySelector(\"button[type='submit']\").click()")

		content = self.cr.get_rendered_page_source()

		if not settings[self.pluginShortName]['username'] in content:
			import IPython
			IPython.embed()
			raise exceptions.CannotAccessException("Could not log in?")

		# self.wg.saveCookies()

		return self.checkCookie()

	def handle_cf(self, content):
		assert content['code'] == 403

		rendered = self.cr.get_rendered_page_source()


	def get_api_json(self, endpoint, postData = None, retry=False):
		if postData:
			postData = {"data" : postData}
			postData = json.dumps(postData, sort_keys=True)

		if endpoint.startswith("http"):
			endpoint_url = endpoint
		else:
			assert endpoint.startswith("/"), "Endpoint isn't a relative path! Passed: '%s'" % endpoint
			endpoint_url = "https://www.patreon.com/api{endpoint}".format(endpoint=endpoint)


		try:
			content = self.cr.xhr_fetch(
					endpoint_url,
					headers ={
						"content-type"    : "application/json",
						# "Referer"         : PATREON_LOGIN_PAGE,
						# "Pragma"          : "no-cache",
						# "Cache-Control"   : "no-cache",
						},
					post_data = postData,
					post_type = 'application/json'
				)


		except Exception as e:
			traceback.print_exc()
			raise exceptions.UnrecoverableFailureException("Wat?")

		try:
			if content['mimetype'] != 'application/vnd.api+json':
				if content['code'] == 403:
					self.handle_cf(content)


				if retry:
					self.log.error("Response isn't JSON. What?")
					with open("bogus_response.json", "w") as fp:
						json.dump(content, fp)

					if content['code'] == 504:
						raise exceptions.RetryException("Gateway time out. Sleeping for a bit.")

					if content['code'] == 502:
						raise exceptions.RetryException("Gateway time out. Sleeping for a bit.")


					import IPython
					IPython.embed()
					raise exceptions.UnrecoverableFailureException("API Response that is not json!")

				else:

					# Retry just once
					self.random_sleep(10,15,60, include_long=False)
					self.cr.blocking_navigate(PATREON_HOME_PAGE)
					self.random_sleep(10,15,60)
					return self.get_api_json(endpoint, postData, retry=True)

			ret = json.loads(content['response'])
			return ret

		except json.JSONDecodeError as e:
			self.log.error("Failure decoding JSON content:")
			self.log.error("	'%s'", content)

			with open("undecodable_response.json", "w") as fp:
				json.dump(content, fp)
			traceback.print_exc()
			raise exceptions.UnrecoverableFailureException("Wat?")


	def current_user_info(self):
		current = self.get_api_json("/current_user?include=pledges&include=follows")
		return current


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



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Misc functions
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def _rid_to_artist_json(self, aid):
		json_str = self._rid_to_artist_name(aid)

		return json.loads(json_str)

	def fetch_with_chrome(self, cr, url):
		ft = cr.Page_getFrameTree()

		frame_id = ft['result']['frameTree']['frame']['id']

		load_options = {

			"disableCache"       : False,
			"includeCredentials" : True,
		}

		result = cr.Network_loadNetworkResource(frameId=frame_id, url=url, options=load_options)

		file_meta = result['result']['resource']

		CHUNKSIZE = 1024 * 1024

		if 'stream' in file_meta:
			stream_id = file_meta['stream']
			s_chunk = cr.IO_read(handle=result['result']['resource']['stream'], size=CHUNKSIZE)
			f_buf = maybe_decode(s_chunk['result'])
			pbar = tqdm.tqdm()
			while s_chunk['result']['eof'] == False:
				s_chunk = cr.IO_read(handle=result['result']['resource']['stream'], size=CHUNKSIZE)
				f_buf += maybe_decode(s_chunk['result'])
				pbar.update(CHUNKSIZE)
			pbar.close()
			return f_buf
		if 'httpStatusCode' in file_meta:
			raise exceptions.FetchFailedException("HTTP status code: %s -> error: %s" % (file_meta['httpStatusCode'], file_meta['netErrorName']))
		else:
			print("No stream at url:", url)
			import pdb
			pdb.set_trace()


