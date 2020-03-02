
import os
import os.path
import traceback
import re
import json
import datetime
import time
import urllib.request

import dateutil.parser
import WebRequest

import flags
from settings import settings


import xascraper.modules.scraper_base
import xascraper.modules.exceptions


def to_base(s, b):
	res = ""
	while s:
		res += "0123456789abcdefghijklmnopqrstuvwxyz"[s%b]
		s //= b
	return res[::-1] or "0"

class GetDA(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "da"
	pluginName = "DaGet"

	ovwMode = "Check Files"

	numThreads = 1

	api_request_id = None
	runtime_id     = None
	csrf_token     = None

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		if self._is_logged_in():
			return True, "Already Logged in"
		# print authCookie, authSecureCookie
		return False, "Do not have DA login Cookies"

	def _is_logged_in(self):
		try:
			content, filename, mimetype = self.wg.getItemChromium("https://www.deviantart.com")
		except WebRequest.FetchFailureError:
			# I think they blacklist your cookie if they decide you're a bot. We need to re-auth in that case
			# Alternatively, there might be a perimeterx cookie somewhere.
			self.wg.clearCookies()
			content, filename, mimetype = self.wg.getItemChromium("https://www.deviantart.com")


		return settings["da"]["username"].lower() in content.lower()

	def getCookie(self):

		if self.checkCookie()[0]:
			return True, "Already logged In"

		login_page = 'https://www.deviantart.com/users/login'
		login_action = '/_sisu/do/signin'
		try:
			soup = self.wg.getSoup(login_page, retryQuantity = 0)
		except WebRequest.FetchFailureError as err:
			with open("%s - Failed da login.html" % time.time(), "wb") as fp:
				fp.write(err.err_content)
			self.log.error("Failed to get login page?")
			self.log.error("Fetch failure reason: %s", err.err_reason)
			self.log.error("Fetch failure code: %s", err.err_code)
			return False, "Login Failed"



		# print prepage
		form = soup.find("form", action=login_action)
		if not form:
			with open("Bad page.html", "w") as fp:
				fp.write(soup.prettify())
			raise xascraper.modules.exceptions.CannotAccessException("DA Scraper is bot-blocked. Please log in manually from your IP to un-wedge.")
		items = form.find_all("input")
		logDict = {}
		for item in items:
			if "name" in item.attrs and "value" in item.attrs:
				# print(item["name"], item["value"])
				logDict[item["name"]] = item["value"]

		# print(logDict)
		if not ("username" in logDict and "password" in logDict):
			raise ValueError("Login form structure changed! Don't know how to log in correctly!	")

		logDict["username"]     = settings["da"]["username"]
		logDict["password"]     = settings["da"]["password"]
		# logDict["ref"]          = 'https://www.deviantart.com/'
		logDict["remember"]  = 1

		time.sleep(5)

		login_post_page = urllib.parse.urljoin(login_page, login_action)

		try:
			pagetext = self.wg.getpage(login_post_page, postData = logDict, addlHeaders={'Referer':login_page}, retryQuantity = 0)
		except WebRequest.FetchFailureError as err:
			failtime = time.time()
			with open("%s - Login failure source.html" % (failtime, ), "w") as fp:
				fp.write(soup.prettify())
			with open("%s - Login failure content.html" % (failtime, ), "w") as fp:
				fp.write(err.err_content.decode("utf-8"))

			self.log.error("Failed to post to login page?")
			self.log.error("Fetch failure reason: %s", err.err_reason)
			self.log.error("Fetch failure code: %s", err.err_code)

			ctnt = WebRequest.as_soup(err.err_content)
			newurl = urllib.parse.urljoin(login_page, ctnt.a['href'])
			next_page = self.wg.getpage(newurl, addlHeaders={'Referer':login_page}, retryQuantity = 0)

			with open("%s - Login failure refered_to.html" % (failtime, ), "w") as fp:
				fp.write(next_page)

			return False, "Login Failed"

		# print pagetext
		if re.search("The username or password you entered was incorrect", pagetext):
			return False, "Login Failed"
		else:
			return True, "Logged In"


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Utility bits
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _checkLoginFromSoup(self, soup):
		ss = str(soup)
		loggedin_str = '"loggedIn":true,"browseShadows":true,"username":"%s"' % settings["da"]["username"]

		if loggedin_str in ss:
			return True
		else:
			return False

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromMeta(self, pageSoup, item_meta, deviation_base):
		# print(pageSoup)

		try:
			if 'download' in item_meta:
				imgurl = item_meta['download']['url']
				self.log.info("Found DDL Link! - %s", imgurl)
				return imgurl

			if deviation_base.get("textContent", None):
				return "Prose"

			media = deviation_base.get('media', None)
			if media:
				if "token" not in media:
					return media['baseUri']

				preferred_order = [
					None,
					"150",
					"200H",
					"300W",
					"250T",
					"350T",
					"400T",
					"preview",
					"social_preview",
					"fullview",
				]
				keep = None

				for try_name in preferred_order:
					for item in media['types']:
						# So for really small images, we don't get the filenames on them, but the entries are present.
						# Because fuck the world, or something
						if try_name and item['t'] == try_name and 'c' in item:
							keep = item
						# else:
						# 	keep = item

				if keep and 'baseUri' in media:
					url = media['baseUri'] + "/" + keep['c'].replace("<prettyName>", media['prettyName']) + "?token=" + media['token'][0]
					print("Want: ", keep)
					print("url:", url)
					return url


		except Exception as e:
			import pdb

			pdb.set_trace()

		raise RuntimeError("No content found! Fixme!")


		# link = pageSoup.find('a', download="")
		# if link:							# Try for DDL (Works for flash and most stories too)
		# 	imgurl = link["href"]
		# 	self.log.info("Found anchor tag - %s", imgurl)
		# 	return imgurl

		# link = pageSoup.find("img", class_="dev-content-full")
		# if link:
		# 	imgurl = link["src"]
		# 	self.log.info("Whoops, had to manually extract Img URL - %s", imgurl)
		# 	return imgurl


		# link = pageSoup.find("img", class_="dev-content-normal")
		# if link:
		# 	imgurl = link["src"]
		# 	self.log.info("Whoops, had to manually extract Img URL - %s", imgurl)
		# 	return imgurl

		# if pageSoup.find("div", class_='journal-wrapper'):
		# 	self.log.info("Item is prose, rather then art.")
		# 	return "Prose"

		# embed = pageSoup.find("iframe", class_='flashtime')
		# if embed:
		# 	self.log.info("Found flash content - %s. Fetching SWF url", embed['src'])
		# 	embed_page = self.wg.getSoup(embed['src'])
		# 	embedurl = embed_page.embed["src"]
		# 	self.log.info("SWF found at %s", embedurl)
		# 	return embedurl

		# self.log.info("Trying for Video Link")
		# try:
		# 	link = pageSoup.findAll("a", attrs={"class" : "b"})[-1]
		# 	if link:

		# 		urlAddr = link["href"]
		# 		linkHandle = urllib.request.urlopen(urlAddr)
		# 		imgurl = linkHandle.geturl()
		# 		return imgurl
		# except Exception:
		# 	return False

	def _getContentDescriptionTitleFromMeta(self, in_meta, item_dat):
		text_content = item_dat.get("textContent", None)
		commentary = in_meta.get("description", None)

		pageDesc = ""

		if text_content:
			if 'html' in text_content:
				pageDesc += text_content['html']['markup']
			else:
				raise RuntimeError("Unknown text content type for item!")

		if text_content and commentary:
			pageDesc += "<br><br>"

		if commentary:
			pageDesc += str(commentary)

		pageTitle = item_dat.get("title", "No Title!")

		tags = in_meta.get("tags", [])

		postTags = [
			tag['name'] for tag in tags
		]

		postTime = dateutil.parser.isoparse(item_dat['publishedTime']).replace(tzinfo=None)

		self.log.info("Post title: %s", pageTitle)
		self.log.info("Post tags: %s", postTags)
		self.log.info("Post date: %s", postTime)

		return pageDesc, pageTitle, postTags, postTime

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		self.log.info("Getting page %s", artPageUrl)

		content = self.wg.getpage(artPageUrl)

		pageSoup = WebRequest.as_soup(content)
		state = self._extract_state(content)

		meta = state['@@entities']

		with open("page.html", "w") as fp:
			fp.write(pageSoup.prettify())

		with open("page.json", "w") as fp:
			fp.write(json.dumps(state, indent=4))

		bulk_items = meta.get("deviation", None)
		item_meta = meta.get("deviationExtended", None)
		if not item_meta:
			raise xascraper.modules.exceptions.CannotFindContentException("Image missing?")
		if not bulk_items:
			raise xascraper.modules.exceptions.CannotFindContentException("Image missing?")

		assert len(item_meta) == 1

		deviation_id, item_meta = item_meta.popitem()

		deviation_base = bulk_items[deviation_id]

		pageDesc, pageTitle, postTags, postTime = self._getContentDescriptionTitleFromMeta(item_meta, deviation_base)
		imgurl = self._getContentUrlFromMeta(pageSoup, item_meta, deviation_base)

		if not imgurl:
			self.log.critical("No image on page = %s", artPageUrl)
			if not self._checkLoginFromSoup(pageSoup):
				# If we've not logged in, relogin.
				raise xascraper.modules.exceptions.NotLoggedInException("Image missing?")

			raise xascraper.modules.exceptions.CannotFindContentException("Image missing?")



		if imgurl == "Prose":
			return self.build_page_ret(status="Prose", fqDlPath=[], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)

		else:

			fname = imgurl.split("/")[-1]
			fname = fname.split("?")[0]
			fname = "{} - {}".format(pageTitle, fname)
			self.log.info("			Filename = %s", fname)
			self.log.info("			FileURL = %s", imgurl)

			# Sanitize filename
			fname = xascraper.modules.scraper_base.makeFilenameSafe(fname)

			# print self.DLFolder, daName, fname
			filePath = os.path.join(dlPathBase, fname)
			if self._checkFileExists(filePath):
				self.log.info("Exists, skipping...")
				return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)
			else:

				headers = {'Referer': artPageUrl}
				# print "Adding referrer info: ", headers
				imgdat = self.wg.getpage(imgurl, addlHeaders=headers)							# Request Image
				if imgdat == "Failed":
					self.log.error("cannot get image")
					return self.build_page_ret(status="Failed", fqDlPath=None)

				# For text, the URL fetcher returns decoded strings, rather then bytes.
				# Therefore, if the file is a string type, we encode it with utf-8
				# so we can write it to a file.
				if isinstance(imgdat, str):
					imgdat = imgdat.encode(encoding='UTF-8')

				filePath = self.save_file(filePath, imgdat)
				if not filePath:
					return self.build_page_ret(status="Failed", fqDlPath=None)

				self.log.info("Successfully got: '%s'", imgurl)

				# return "Succeeded", filePath, pageDesc, pageTitle									# Return Success
				return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)




		raise RuntimeError("How did this ever execute?")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		if artist == 'welcome':
			# Ugh, bug
			raise xascraper.modules.exceptions.AccountDisabledException("Account seems to have been removed!")


		basePage = "https://%s.deviantart.com/" % artist
		try:
			page = self.wg.getpage(basePage)
		except WebRequest.FetchFailureError as e:
			if e.err_code == 404:
				raise xascraper.modules.exceptions.AccountDisabledException("Account seems to have been removed!")
			else:
				raise xascraper.modules.exceptions.CannotAccessException("Failed to access page for artist %s. HTTP Error %s!" % (artist, e.err_code))

		meta = self._extract_state(page)




		art_count = meta.get("profileOwner", {}).get("stats", {}).get("deviations")

		if art_count is None:
			raise xascraper.modules.exceptions.AccountDisabledException("Could not retreive artist item quantity!")

		# There seems to be a bug here where the number of reported gallery items are actual gallery item counts + 1
		# No idea where the +1 thing is
		if art_count > 1:
			art_count -= 1

		self.log.info("Artist '%s' has %s art items!", artist, art_count)
		return art_count


	def _extract_state(self, page_text):
		'''
			this.runtimeid = t.requestid + "-" + (new Date).getTime().toString(36),

			get_instanceid: function() {
				return this.daid + "+" + this.runtimeid
			},
			get_local_logid: function() {
				return this.get_pageview_ctr() + "." + this.event_ctr
			},
			get_client_logid: function() {
				return this.runtimeid + "-" + this.get_local_logid()
			},
			get_pageview_ctr: function() {
				return Math.max(1, this.impression_ctr)
			},
		'''


		res = re.search(r"window\.__INITIAL_STATE__ = JSON\.parse\((.*?)\);", page_text)

		if not res:
			raise xascraper.modules.exceptions.AccountDisabledException("Initial state entry not found!!")

		jstr = res.group(1)
		# Yes, this is double nested. I have no idea why.
		meta = json.loads(json.loads(jstr))

		if not meta:
			raise xascraper.modules.exceptions.AccountDisabledException("Could not retreive artist item quantity!")


		# Update the request id and csfr token (if needed)
		req_id   = meta.get("@@config", {}).get("requestId", None)
		csrf_tok = meta.get("@@config", {}).get("csrfToken", None)

		if req_id:
			self.api_request_id = req_id

			# Always return one for events and page views (because fuck their stats)
			self.runtime_id     = "%s-%s-1.1" % (self.api_request_id, to_base(int(time.time() * 1000), 36))

		if csrf_tok:
			self.csrf_token     = csrf_tok


		return meta

	def __api_call(self, url, post_params):
		# We need these to make api calls
		assert self.runtime_id
		assert self.csrf_token

		post_params['_csrf']   = self.csrf_token
		post_params['dapiIid'] = self.runtime_id

		ret = self.wg.getpage(url, postData=post_params)

		ret = json.loads(ret)

		return ret


	def _get_gallery(self, artist, gallery_id):
		tgt_url = "https://www.deviantart.com/dapi/v1/gallery/{gallery_id}?iid={iid}&mp=1".format(gallery_id=gallery_id, iid=self.runtime_id)

		offset = 0
		items  = []
		while True:
			params = {
				"username" : artist,
				"offset"   : offset * 24,
				"limit"    : 24,
			}

			offset += 1

			dat = self.__api_call(tgt_url, params)
			content = dat['content']

			if not content['has_more']:
				break

			for item in content['results']:

				soup = WebRequest.as_soup(item.get('html', ""))
				link = soup.find("a", class_="torpedo-thumb-link")

				items.append(link['href'])

		self.log.info("Found %s items in gallery folder %s for artist %s", len(items), gallery_id, artist)
		return set(items)

	def _getGalleries(self, artist):
		root_url = "https://www.deviantart.com/%s/gallery/" % (artist, )

		root_page = self.wg.getpage(root_url)
		meta = self._extract_state(root_page)


		gallery_ids = meta.get("folders", {}).get("galleryFolders", {}).get("ids", [])

		# print("Galleries: ", gallery_ids)

		ret = set()
		for gallery_id in gallery_ids:

			new = self._get_gallery(artist, gallery_id)
			ret |= new

		return ret


