
import os
import os.path
import traceback
import re
import bs4
import dateparser
import urllib.request
import flags
from settings import settings
import urllib.parse

import util.captcha2upload
import rewrite.modules.scraper_base

class GetFA(rewrite.modules.scraper_base.ScraperBase, util.captcha2upload.CaptchaSolverMixin):

	settingsDictKey = "fa"
	pluginName = "FaGet"

	urlBase = "http://www.furaffinity.net/"


	ovwMode = "Check Files"

	numThreads = 3



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):

		userID = re.search(r"<Cookie a=[0-9a-f\-]*? for \.furaffinity\.net/>", "%s" % self.wg.cj)
		sessionID = re.search(r"<Cookie b=[0-9a-f\-]*? for \.furaffinity\.net/>", "%s" % self.wg.cj)
		if userID and sessionID:
			return True, "Have FA Cookies:\n	%s\n	%s" % (userID.group(0), sessionID.group(0))

		return False, "Do not have FA login Cookies"


	def getCookie(self):

		if self.checkCookie()[0] is True:
			self.log.warn("Do not need to log in!")
			return "Logged In"


		balance = self.captcha_solver.getbalance()
		self.log.info("Captcha balance: %s", balance)

		login_pg    = self.wg.getpage('https://www.furaffinity.net/login/')
		captcha_img = self.wg.getpage('https://www.furaffinity.net/captcha.jpg')

		with open("img.jpg", "wb") as fp:
			fp.write(captcha_img)

		self.log.info("Solving captcha. Please wait")
		captcha_result = self.captcha_solver.solve(filedata=captcha_img, filename='captcha.jpg')
		self.log.info("Captcha solving service result: %s", captcha_result)
		values = {
			'action'               : 'login',
			'name'                 : settings['fa']['username'],
			'pass'                 : settings['fa']['password'],
			'g-recaptcha-response' : "",
			'use_old_captcha'      : 1,
			'captcha'              : captcha_result,
			'login'                : 'Login to FurAffinity',
		}


		pagetext = self.wg.getpage('https://www.furaffinity.net/login/?url=/', postData = values)

		if self.checkCookie()[0] is True:
			return "Logged In"
		else:
			return "Login Failed"


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromPage(self, pgIn):

		# TODO: Proper page parsing, rather then regexes

		regx1 = re.compile(r'[\"\']((?:https:)?//d\.facdn\.net\/[^\'\"]*?)[\"\']>\s?Download\s?</a>')
		reResult = regx1.search(pgIn)

		if reResult:
			imgurl = reResult.group(1)
			self.log.info("Found direct download URL : %s" % imgurl)
			return imgurl


		regx2 = re.compile('var full_url *?= [\'\"]([^\'\"]*?)[\"\']')							# Extract Image location from javascript
		reResult = regx2.search(pgIn)


		if reResult:
			imgurl = reResult.group(1)
			self.log.info("Found Image URL : %s" % imgurl)

			return imgurl

		regx2 = re.compile(r'<param name="movie" *?value=[\'\"]([^\s\'\"]*?)[\"\']')

		reResult = regx2.search(pgIn)
		if reResult:
			imgurl = reResult.group(1)

			self.log.info("Found Flash URL : %s" % imgurl)
			return imgurl

		return False


	def _getContentDescriptionTitleFromSoup(self, soup):

		pageDesc = ""
		pageTitle = ""
		commentaryTd = soup.find("td", attrs={"valign":"top", "align":"left", "class":"alt1", "width":"70%"})
		if commentaryTd:

			# Pull out all the items in the commentary <td>
			# print("Commentary = ", commentaryTd)

			for item in commentaryTd.children:
				content = str(item).rstrip().lstrip()
				pageDesc += content


		titleCont = soup.find("td", attrs={"valign":"top", "align":"left", "class":"cat", "width":"70%"})
		if titleCont and "- by" in titleCont.text:
			pageTitle = titleCont.find("b").text.rstrip().lstrip()
			pageTitle = str(pageTitle)

		datespan = soup.find('span', class_='popup_date')
		postTime = dateparser.parse(datespan['title'])

		tagdiv = soup.find('div', id='keywords')
		if tagdiv:
			tags = tagdiv.find_all("a")
			tags = [tag.get_text().strip() for tag in tags]
		else:
			tags = []

		return pageDesc, pageTitle, tags, postTime


	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		self.log.info("Getting page %s", artPageUrl)

		pageCtnt = self.wg.getpage(artPageUrl)



		imgurl = self._getContentUrlFromPage(pageCtnt)

		if not imgurl:
			self.log.error("OH NOES!!! No image on page: %s" % artPageUrl)

			return self.build_page_ret(status="Failed", fqDlPath=None)								# Return Fail


		if not "http:" in imgurl:						# Fa is for some bizarre reason, leaving the 'http:' off some of their URLs
			imgurl = "http:%s" % imgurl

		fileTypeRe = re.compile(r".+\.")
		fileNameRe = re.compile(r".+/")						# Pull out filename only

		fname = fileNameRe.sub("" , imgurl)
		ftype = fileTypeRe.sub("" , fname)					# Pull out filename only

		self.log.info("			Filename = " + fname)
		self.log.info("			File Type = " + ftype)
		self.log.info("			FileURL  = " + imgurl)


		try:
			filePath = os.path.join(dlPathBase, fname)
			pageDesc, pageTitle, postTags, postTime = self._getContentDescriptionTitleFromSoup(bs4.BeautifulSoup(pageCtnt, "lxml"))
			self.log.info("			postTags  = " + postTags)
			self.log.info("			postTime  = " + postTime)

		except:
			print("file path issue")

			traceback.print_exc()

			self.log.error("file path issue")
			self.log.error("%s", artPageUrl)
			self.log.error("%s", traceback.format_exc())
			self.log.exception("Error with path joining")
			return self.build_page_ret(status="Failed", fqDlPath=None)


		if self._checkFileExists(filePath):
			self.log.info("Exists, skipping...")
			return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)
		else:

			imgdat = self.wg.getpage(imgurl)							# Request Image

			if imgdat == "Failed":
				self.log.error("cannot get image %s" % imgurl)
				self.log.error("source gallery page: %s" % artPageUrl)
				return self.build_page_ret(status="Failed", fqDlPath=None)

			errs = 0
			imgFile = None

			while not imgFile:
				try:
					# For text, the URL fetcher returns decoded strings, rather then bytes.
					# Therefore, if the file is a string type, we encode it with utf-8
					# so we can write it to a file.
					if isinstance(imgdat, str):
						imgdat = imgdat.encode(encoding='UTF-8')

					imgFile = open(filePath, "wb")						# Open file for saving image (Binary)
					imgFile.write(imgdat)							# Write Image to File
					imgFile.close()
				except IOError:
					try:
						imgFile.close()
					except:
						pass
					errs += 1
					self.log.critical("Error attempting to save image file - %s" % filePath)
					if errs > 3:
						self.log.critical("Could not open file for writing!")
						raise



			self.log.info("Successfully got: " + imgurl)
			return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)

		raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://www.furaffinity.net/user/%s/" % artist
		page = self.wg.getSoup(basePage)

		tds = page.find("td", align="right", text="Statistics")

		stats = tds.parent.parent.text
		for line in stats.splitlines():
			line = line.rstrip(" 	").lstrip(" 	")
			if "Submissions: " in line:

				num = line.split(":")[-1]
				return int(num)

		raise LookupError("Could not retreive artist item quantity!")


	def _getItemsOnPage(self, inSoup):

		links = set()
		pageContainers = inSoup("figure", id=re.compile(r"sid-\d+"))

		for item in pageContainers:
			link = urllib.parse.urljoin(self.urlBase, item.find("a")["href"])
			links.add(link)

		return links


	def _getGalleries(self, artist):

		galleries = ["http://www.furaffinity.net/gallery/%s/%s/",     # Format is "..../{artist-name}/{page-no}/"
					"http://www.furaffinity.net/scraps/%s/%s/"]



		ret = set()								# Declare array of links


		for galleryUrlBase in galleries:
			print("Retreiving gallery", galleryUrlBase)
			pageNo = 1
			while 1:

				if not flags.run:
					break

				turl = galleryUrlBase % (artist, pageNo)
				self.log.info("Getting = " + turl)
				pageSoup = self.wg.getSoup(turl)							# Request Image
				if pageSoup == "Failed":
					self.log.error("Cannot get Page: %s" % turl)
					break


				new = self._getItemsOnPage(pageSoup)
				if len(new) == 0 or flags.run == False:
					self.log.info("No more images. At end of gallery.")
					break
				ret |= new
				self.log.info("Retreived gallery page with %s links. Total links so far %s.", len(new), len(ret))

				pageNo += 1


		self.log.info("Found %s links" % (len(ret)))

		return ret


