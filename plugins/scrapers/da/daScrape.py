
import os
import os.path
import traceback
import re
import bs4
import urllib.request
import flags
from settings import settings


import plugins.scrapers.ScraperBase


class GetDA(plugins.scrapers.ScraperBase.ScraperBase):

	settingsDictKey = "da"
	pluginName = "DaGet"

	ovwMode = "Check Files"

	numThreads = 8


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		authCookie			=	re.search(r"<Cookie auth=[_%0-9a-z]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)
		authSecureCookie	=	re.search(r"<Cookie auth_secure=[_%0-9a-z]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)
		userinfo			=	re.search(r"<Cookie userinfo=[_%0-9a-z]*? for \.deviantart\.com/>", "%s" % self.wg.cj, re.IGNORECASE)

		if authCookie and authSecureCookie and userinfo:
			return True, "Have DA Cookies:\n	%s\n	%s\n	%s" % (authCookie.group(0), authSecureCookie.group(0), userinfo.group(0))
		# print authCookie, authSecureCookie
		return False, "Do not have DA login Cookies"


	def getCookie(self):

		prepage = self.wg.getpage('https://www.deviantart.com/users/login')
		# print prepage
		soup = bs4.BeautifulSoup(prepage, "lxml")
		form = soup.find("form", action="https://www.deviantart.com/users/login")
		items = form.find_all("input")
		logDict = {}
		for item in items:
			if "name" in item.attrs and "value" in item.attrs:
				# print(item["name"], item["value"])
				logDict[item["name"]] = item["value"]

		# print(logDict)
		if not "username" in logDict and "password" in logDict:
			raise ValueError("Login form structure changed! Don't know how to log in correctly!	")
		logDict["username"] = settings["da"]["username"]
		logDict["password"] = settings["da"]["password"]

		pagetext = self.wg.getpage('https://www.deviantart.com/users/login', postData = logDict)

		# print pagetext
		if re.search("The username or password you entered was incorrect", pagetext):
			return "Login Failed"
		else:
			return "Logged In"


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromSoup(self, soupIn):

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


		return pageDesc, pageTitle

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		self.log.info("Getting page %s", artPageUrl)

		pageSoup = self.wg.getSoup(artPageUrl)


		imgurl = self._getContentUrlFromSoup(pageSoup)
		pageDesc, pageTitle = self._getContentDescriptionTitleFromSoup(pageSoup)

		if not imgurl:
			self.log.critical("OH NOES!!! No image on page = %s", artPageUrl)
			# print mpgctnt
			return "Failed", ""

		if imgurl == "Prose":
			return "Succeeded", None, pageDesc, pageTitle

		else:

			regx3 = re.compile("http://.+/")							# Pull out filename only
			fname = regx3.sub("" , imgurl)
			fname = fname.split("?")[0]
			self.log.info("			Filename = " + fname)
			self.log.info("			FileURL = " + imgurl)

			# Sanitize filename
			fname = "".join([x for x in fname if x.isalpha() or x.isdigit() or x == "_" or x == "-" or x == "." or x == "(" or x == ")"	])
			# print self.DLFolder, daName, fname
			filePath = os.path.join(dlPathBase, fname)
			if self._checkFileExists(filePath):
				self.log.info("Exists, skipping...")
				return "Exists", filePath, pageDesc, pageTitle
			else:

				headers = {'Referer': artPageUrl}
				# print "Adding referrer info: ", headers
				imgdat = self.wg.getpage(imgurl, addlHeaders=headers)							# Request Image
				if imgdat == "Failed":
					self.log.error("cannot get image")
					return "Failed", ""

				errs = 0
				fp = None

				while not fp:
					try:
						# For text, the URL fetcher returns decoded strings, rather then bytes.
						# Therefore, if the file is a string type, we encode it with utf-8
						# so we can write it to a file.
						if isinstance(imgdat, str):
							imgdat = imgdat.encode(encoding='UTF-8')

						fp = open(filePath, "wb")								# Open file for saving image (Binary)
						fp.write(imgdat)
						fp.close()
					except IOError:
						try:
							fp.close()
						except Exception:
							pass
						errs += 1
						self.log.critical("Error attempting to save image file - %s", filePath)
						if errs > 3:
							self.log.critical("Could not open file for writing!")
							return "Failed", ""
														# Write Image to File

					except Exception:
						self.log.error("Error saving image - what?")
						self.log.error("Source URL: '%s'", artPageUrl)
						self.log.error(type(imgdat))

						self.log.error(traceback.format_exc())


				self.log.info("Successfully got: " + imgurl)
				return "Succeeded", filePath, pageDesc, pageTitle									# Return Success




		raise RuntimeError("How did this ever execute?")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://%s.deviantart.com/" % artist
		page = self.wg.getSoup(basePage)
		div = page.find("div", class_="pbox pppbox")
		if not div:
			raise LookupError("Could not retreive artist item quantity!")
		return int(div.find("strong").text.replace(',', ''))

	def _getItemsOnPage(self, inSoup):
		mainSection = inSoup.find('div', attrs={"name" : "gmi-ResourceStream", "id" : "gmi-ResourceStream"})
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

