
import os
import os.path
import traceback
import re
import datetime
import time
import urllib.request

import WebRequest
import bs4

import flags
from settings import settings


import xascraper.modules.scraper_base
import xascraper.modules.exceptions

class GetDA(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "da"
	pluginName = "DaGet"

	ovwMode = "Check Files"

	numThreads = 1

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		authCookie			=	re.search(r"<Cookie auth=[\_\%0-9a-z]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)
		authSecureCookie	=	re.search(r"<Cookie auth_secure=[\_\%0-9a-z]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)
		userinfo			=	re.search(r"<Cookie userinfo=[\_\%0-9a-z\-]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)

		if authCookie and authSecureCookie and userinfo:
			if self._is_logged_in():
				return True, "Have DA Cookies:\n	%s\n	%s\n	%s" % (authCookie.group(0), authSecureCookie.group(0), userinfo.group(0))
		# print authCookie, authSecureCookie
		return False, "Do not have DA login Cookies"

	def _is_logged_in(self):
		soup = self.wg.getSoup("https://www.deviantart.com/")

		user_1 = soup.find('span', class_='username')

		return user_1 and settings["da"]["username"].lower() in user_1.get_text(strip=True).lower()

	def getCookie(self):

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
				print(item["name"], item["value"])
				logDict[item["name"]] = item["value"]

		# print(logDict)
		if not "username" in logDict and "password" in logDict:
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
		pass

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromSoup(self, soupIn):
		# print(soupIn)

		link = soupIn.find('a',  { "class" : "dev-page-download" })
		if link:							# Try for DDL (Works for flash and most stories too)
			imgurl = link["href"]
			self.log.info("Found DDL Link! - %s", imgurl)
			return imgurl

		self.log.info("Trying for Manual full-content URL")
		link = soupIn.find("img", class_="dev-content-full")
		if link:
			imgurl = link["src"]
			self.log.info("Whoops, had to manually extract Img URL - %s", imgurl)
			return imgurl


		self.log.info("Trying for Manual normal-content URL")
		link = soupIn.find("img", class_="dev-content-normal")
		if link:
			imgurl = link["src"]
			self.log.info("Whoops, had to manually extract Img URL - %s", imgurl)
			return imgurl

		if soupIn.find("div", class_='journal-wrapper'):
			self.log.info("Item is prose, rather then art.")
			return "Prose"

		self.log.info("Trying for Video Link")
		try:
			link = soupIn.findAll("a", attrs={"class" : "b"})[-1]
			if link:

				urlAddr = link["href"]
				linkHandle = urllib.request.urlopen(urlAddr)
				imgurl = linkHandle.geturl()
				return imgurl
		except Exception:
			return False

	def _getContentDescriptionTitleFromSoup(self, inSoup):

		pageDesc = ""
		pageTitle = ""

		text_content = inSoup.find("div", class_='journal-wrapper')
		commentary = inSoup.find("div", attrs={"class" : "text block"})

		pageDesc = ""

		if text_content:
			textContentTag = text_content.extract()
			pageDesc += str(textContentTag)

		if text_content and commentary:
			pageDesc += "<br><br>"

		if commentary:
			pageDescTag = commentary.extract()
			pageDesc += str(pageDescTag)

		titleCont = inSoup.find("div", class_="dev-title-container")
		if titleCont:
			pageTitle = titleCont.find("h1").find("a").text.rstrip().lstrip()
			pageTitle = str(pageTitle)

		tags = inSoup.find_all("a", class_='discoverytag')

		postTags = [
			tag['data-canonical-tag'] for tag in tags
		]


		meta = inSoup.find("div", class_='dev-metainfo-details')
		postdate = meta.find('span', ts=True)
		ts = int(postdate['ts'])
		postTime = datetime.datetime.fromtimestamp(ts)

		self.log.info("Post tags: %s", postTags)
		self.log.info("Post date: %s", postTime)

		return pageDesc, pageTitle, postTags, postTime

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		self.log.info("Getting page %s", artPageUrl)

		pageSoup = self.wg.getSoup(artPageUrl)


		if pageSoup.find(class_='matureoption'):
			self.log.critical("You seem to not be logged on (or have mature content disabled)?")
			raise xascraper.modules.exceptions.NotLoggedInException("You seem to not be logged on (or have mature content disabled)?")



		imgurl = self._getContentUrlFromSoup(pageSoup)
		pageDesc, pageTitle, postTags, postTime = self._getContentDescriptionTitleFromSoup(pageSoup)

		if not imgurl:
			self.log.critical("OH NOES!!! No image on page = %s", artPageUrl)
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
		basePage = "http://%s.deviantart.com/" % artist
		try:
			page = self.wg.getSoup(basePage)
		except WebRequest.FetchFailureError as e:
			if e.err_code == 404:
				raise xascraper.modules.exceptions.AccountDisabledException("Account seems to have been removed!")
			else:
				raise xascraper.modules.exceptions.CannotAccessException("Failed to access page for artist %s. HTTP Error %s!" % (artist, e.err_code))

		group_entry = page.find("a", href="#super-secret-why")

		if group_entry and "Group" in group_entry.get_text():
			self.log.error("You seem to have accidentally added a DA Group (%s) to the scrape targets!", artist)
			raise xascraper.modules.exceptions.AccountDisabledException("You seem to have accidentally added a DA Group to the scrape targets!")




		div = page.find("div", class_="pbox pppbox")
		if not div:
			raise xascraper.modules.exceptions.AccountDisabledException("Could not retreive artist item quantity!")
		return int(div.find("strong").text.replace(',', ''))

	def _getItemsOnPage(self, inSoup):
		mainSection = inSoup.find('div', attrs={"name" : "gmi-GZone", "id" : "gmi-GZone"})
		links = mainSection.findAllNext("a", class_="torpedo-thumb-link")
		ret = set()
		for link in links:
			ret.add(link["href"])

		return ret

	def _getGalleries(self, artist):
		subGalleries = ["http://%s.deviantart.com/gallery/?catpath=/&offset=%s", "http://%s.deviantart.com/gallery/?catpath=scraps&offset=%s"] #, "http://%s.deviantart.com/gallery/?offset=%s"]
		ret = set()
		for gallery in subGalleries:
			loopCounter = 0
			while 1:

				pageUrl = gallery % (artist, loopCounter * 24)
				pageSoup = self.wg.getSoup(pageUrl)
				new = self._getItemsOnPage(pageSoup)
				if len(new) == 0 or flags.run == False:
					self.log.info("No more images. At end of gallery.")
					break
				ret |= new
				self.log.info("Retreived gallery page with %s links. Total links so far %s.", len(new), len(ret))
				loopCounter += 1

		return ret




if __name__ == '__main__':

	import multiprocessing.managers
	import logSetup
	logSetup.initLogging()

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	namespace = manager.Namespace()
	namespace.run=True



	ins = GetDA()
	have_cookie, message = ins.checkCookie()
	print('have_cookie', have_cookie)
	if not have_cookie:
		ins.getCookie()



	ins.go(ctrlNamespace=namespace)

	# print(ins)
	# print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	# ins._getArtPage("xxxx", 'http://samus9450.deviantart.com/art/SAMUS-ZERO-SUIT-SEXY-3-603835374', 'testtt')
	# ins.getArtist('testtt', ctrlNamespace=namespace)


