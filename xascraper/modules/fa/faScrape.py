
import os
import os.path
import traceback
import re
import time
import urllib.parse
import dateparser
import WebRequest
import flags
from settings import settings

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class GetFA(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "fa"
	pluginName = "FaGet"

	urlBase = "http://www.furaffinity.net/"


	ovwMode = "Check Files"

	numThreads = 1

	sleep_time = 6

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		userID = re.search(r"<Cookie a=[0-9a-f\-]*? for \.furaffinity\.net/>", "%s" % self.wg.cj)
		sessionID = re.search(r"<Cookie b=[0-9a-f\-]*? for \.furaffinity\.net/>", "%s" % self.wg.cj)
		if not (userID and sessionID):
			return False, "Do not have FA login Cookies"

		settings_page = self.wg.getpage('http://www.furaffinity.net/controls/user-settings/')
		if '<a id="my-username" class="top-heading hideonmobile" href="' in settings_page:
			return True, "Have FA Cookies:\n	%s\n	%s" % (userID.group(0), sessionID.group(0))

		self.log.warning("Not logged in!")

		return False, "Do not have FA login Cookies"


	def getCookie(self):
		if self.checkCookie()[0] is True:
			self.log.warn("Do not need to log in!")
			return "Logged In"

		solver = None
		if '2captcha' in settings['captcha']:
			solver_temp = WebRequest.TwoCaptchaSolver(api_key = settings['captcha']['2captcha']['api_key'], wg=self.wg)
			balance = float(solver_temp.getbalance())

			self.log.info("2Captcha balance: %s", balance)
			if balance > 0:
				solver = solver_temp
		if not solver and 'anti-captcha' in settings['captcha']:
			solver_temp = WebRequest.AntiCaptchaSolver(api_key = settings['captcha']['anti-captcha']['api_key'], wg=self.wg)
			balance = float(solver_temp.getbalance())
			self.log.info("Anti-Captcha balance: %s", balance)
			if balance > 0:
				solver = solver_temp

		if not solver:
			self.log.error("No captcha solver configured (or no solver with a non-zero balance)! Cannot continue!")
			return "Login Failed"


		login_pg    = self.wg.getpage('https://www.furaffinity.net/login/?mode=imagecaptcha')
		captcha_img = self.wg.getpage('https://www.furaffinity.net/captcha.jpg')

		with open("img.jpg", "wb") as fp:
			fp.write(captcha_img)

		self.log.info("Solving captcha. Please wait")
		captcha_result = solver.solve_simple_captcha(filedata=captcha_img, filename='captcha.jpg')
		self.log.info("Captcha solving service result: %s", captcha_result)
		values = {
			'action'               : 'login',
			'name'                 : settings['fa']['username'],
			'pass'                 : settings['fa']['password'],
			'g-recaptcha-response' : "",
			'use_old_captcha'      : 1,
			'captcha'              : captcha_result,
			'login'                : 'Login to Fur Affinity',
		}


		pagetext = self.wg.getpage('https://www.furaffinity.net/login/?ref=https://www.furaffinity.net/', postData = values)

		if self.checkCookie()[0] is True:
			return True, "Logged In"
		else:
			return False, "Login Failed"


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromPage(self, pgIn):

		# TODO: Proper page parsing, rather then regexes

		regx1 = re.compile(r'[\"\']((?:https:)?//d\.facdn\.net\/[^\'\"]*?\w)[\"\']>\s?Download\s?</a>')
		reResult = regx1.search(pgIn)

		if reResult:
			imgurl = reResult.group(1)
			self.log.info("Found direct download URL : %s", imgurl)
			return imgurl


		regx2 = re.compile('var full_url *?= [\'\"]([^\'\"]*?)[\"\']')							# Extract Image location from javascript
		reResult = regx2.search(pgIn)


		if reResult:
			imgurl = reResult.group(1)
			self.log.info("Found Image URL : %s", imgurl)

			return imgurl

		regx2 = re.compile(r'<param name="movie" *?value=[\'\"]([^\s\'\"]*?)[\"\']')

		reResult = regx2.search(pgIn)
		if reResult:
			imgurl = reResult.group(1)

			self.log.info("Found Flash URL : %s", imgurl)
			return imgurl

		return False


	def _getContentDescriptionTitleFromSoup(self, soup):

		pageDesc = ""
		pageTitle = ""
		commentaryTd = soup.find("div", class_='submission-description')
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

		tagdiv = soup.find('section', class_='tags-row')
		if tagdiv:
			tags = tagdiv.find_all("a")
			tags = [tag.get_text().strip() for tag in tags]
		else:
			tags = []

		return pageDesc, pageTitle, tags, postTime


	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		self.log.info("Getting page %s", artPageUrl)

		try:

			pageCtnt = self.wg.getpage(artPageUrl)
		except Exception as e:
			self.log.info("Sleeping %s seconds to avoid rate-limiting", self.sleep_time)
			time.sleep(self.sleep_time)
			raise e


		if 'The submission you are trying to find is not in our database.' in pageCtnt:
			self.log.warning("Content has been removed!")
			self.log.info("Sleeping %s seconds to avoid rate-limiting", self.sleep_time)
			time.sleep(self.sleep_time)
			raise exceptions.ContentRemovedException("Item has been removed")

		imgurl = self._getContentUrlFromPage(pageCtnt)

		if not imgurl:
			self.log.error("OH NOES!!! No image on page: %s", artPageUrl)
			raise exceptions.ContentRemovedException("No image found on page: %s" % artPageUrl)



		if "http:" not in imgurl:
			imgurl = "http:%s" % imgurl

		fileTypeRe = re.compile(r".+\.")
		fileNameRe = re.compile(r".+/")						# Pull out filename only

		fname = fileNameRe.sub("" , imgurl)
		ftype = fileTypeRe.sub("" , fname)					# Pull out filename only

		self.log.info("			Filename = %s", fname)
		self.log.info("			File Type = %s", ftype)
		self.log.info("			FileURL  = %s", imgurl)

		try:
			filePath = os.path.join(dlPathBase, fname)
			pageDesc, pageTitle, postTags, postTime = self._getContentDescriptionTitleFromSoup(WebRequest.as_soup(pageCtnt))
			self.log.info("			postTags  = %s", postTags)
			self.log.info("			postTime  = %s", postTime)

		except Exception:
			print("file path issue")

			traceback.print_exc()

			self.log.error("file path issue")
			self.log.error("%s", artPageUrl)
			self.log.error("%s", traceback.format_exc())
			self.log.exception("Error with path joining")
			return self.build_page_ret(status="Failed", fqDlPath=None)


		if self._checkFileExists(filePath):
			self.log.info("Exists, skipping...")
			self.log.info("Sleeping %s seconds to avoid rate-limiting", self.sleep_time)
			time.sleep(self.sleep_time)
			return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)
		else:

			imgdat = self.wg.getpage(imgurl)							# Request Image

			if imgdat == "Failed":
				self.log.error("cannot get image %s", imgurl)
				self.log.error("source gallery page: %s", artPageUrl)
				return self.build_page_ret(status="Failed", fqDlPath=None)

			# For text, the URL fetcher returns decoded strings, rather then bytes.
			# Therefore, if the file is a string type, we encode it with utf-8
			# so we can write it to a file.
			if isinstance(imgdat, str):
				imgdat = imgdat.encode(encoding='UTF-8')

			filePath = self.save_file(filePath, imgdat)
			if not filePath:
				return self.build_page_ret(status="Failed", fqDlPath=None)

			self.log.info("Successfully got: '%s'",  imgurl)

			self.log.info("Sleeping %s seconds to avoid rate-limiting", self.sleep_time)
			time.sleep(self.sleep_time)

			return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=pageDesc, pageTitle=pageTitle, postTags=postTags, postTime=postTime)

		raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://www.furaffinity.net/user/%s/" % artist
		page = self.wg.getSoup(basePage)
		pgstr = str(page)
		if 'has voluntarily disabled access to their account and all of its contents.' in pgstr:
			self.log.warning("Disabled account!")
			raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")
		if 'The page you are trying to reach has been deactivated by the owner.' in pgstr:
			self.log.warning("Disabled account!")
			raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")
		if 'This user cannot be found.' in pgstr:
			self.log.warning("Account not found!")
			raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")

		# This is HORRIBLE
		containers = page.find_all("div", class_="userpage-section-right")
		for container in containers:
			if container.h2 and "Stats" in container.h2.get_text(strip=True):
				for div_section in container.find_all("div", class_='cell'):
					for span in div_section.find_all("span"):
						if span and "Submissions" in span.get_text(strip=True):
							num = str(span.next_sibling)
							return int(num)

		raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")


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

		ret = set()

		for galleryUrlBase in galleries:
			self.log.info("Retreiving gallery %s", galleryUrlBase)

			for pageNo in range(999999):
				if not flags.run:
					return []

				turl = galleryUrlBase % (artist, pageNo)
				pageSoup = self.wg.getSoup(turl)							# Request Image
				if pageSoup == "Failed":
					self.log.error("Cannot get Page: %s", turl)
					break

				if 'has voluntarily disabled access to their account and all of its contents.' in str(pageSoup):
					self.log.warning("Disabled account!")
					return ret

				new = self._getItemsOnPage(pageSoup)
				if not new or flags.run is False:
					self.log.info("No more images. At end of gallery.")
					break

				ret |= new
				self.log.info("Retreived gallery page with %s links. Total links so far %s.", len(new), len(ret))

				self.log.info("Sleeping %s seconds to avoid rate-limiting", self.sleep_time)
				time.sleep(self.sleep_time)

		self.log.info("Found %s links", len(ret))

		return ret

