
import os
import os.path
import traceback
import re
import bs4
import json
import urllib.request
import urllib.parse
from settings import settings
import flags

import rewrite.modules.scraper_base

class GetPX(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "px"
	pluginName     = "PxGet"

	urlBase         = "http://www.pixiv.net/"
	ovwMode         = "Check Files"

	numThreads      = 5


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		userID_1 = re.search(r"<Cookie PHPSESSID=[0-9a-f_]*? for \.pixiv\.net/>", "%s" % self.wg.cj, re.IGNORECASE)
		userID_2 = re.search(r"<Cookie p_ab_id=[0-9a-f_]*? for \.pixiv\.net/>", "%s" % self.wg.cj, re.IGNORECASE)
		if all([userID_1, userID_2]):
			return True, "Have Pixiv Cookie:\n	%s -> %s" % (userID_1.group(0), userID_2.group(0))

		return False, "Do not have Pixiv Cookies"

	def getCookie(self):
		self.log.info("Pixiv Getting cookie")

		soup = self.wg.getSoup('https://accounts.pixiv.net/login', addlHeaders={'Referer': 'https://www.pixiv.net/'})
		container = soup.find("div", id='old-login')

		inputs = container.find_all("input")
		logondict = {}
		for input_item in inputs:
			if input_item.has_attr('name') and input_item.has_attr('value'):
				key = input_item['name']
				val = input_item['value']
				logondict[key] = val

		logondict["pixiv_id"] = settings[self.settingsDictKey]["username"]
		logondict["password"] = settings[self.settingsDictKey]["password"]

		pagetext = self.wg.getpage('https://accounts.pixiv.net/login', postData = logondict, addlHeaders={'Referer': 'https://accounts.pixiv.net/login'})

		self.wg.syncCookiesFromFile()
		if '<a href="/logout.php?return_to=%2F" data-text-confirm="ログアウトします。よろしいですか？" onclick="return confirm(this.getAttribute(\'data-text-confirm\'))" class="item header-logout">ログアウト</a>' in pagetext:
			return True, "Logged In"
		else:
			return False, "Login Failed"

	def checkLogin(self):

		if not self.checkCookie()[0]:
			ok, message = self.getCookie()
			if not ok:
				raise RuntimeError("Could not log in?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getManga(self, artistName, mangaAddr, dlPath, parentSoup, sourceUrl):
		self.log.info("Params = %s, %s, %s, %s", artistName, mangaAddr, dlPath, sourceUrl)

		successed = True

		soup = self.wg.getSoup(mangaAddr, addlHeaders={'Referer': sourceUrl})			# Spoof the referrer to get the big image version

		if soup.title:
			mangaTitle = soup.title.get_text()
			mangaTitle = re.sub('[\\/:*?"<>|]', "", mangaTitle)
			self.log.info("Title : %s" % (mangaTitle))
		else:
			mangaTitle = None

		scripts = soup.find_all("script", text=re.compile(r"pixiv\.context\.originalImages\["))
		if not scripts:
			return "Failed", ""

		images = []
		img_idx = 1
		for script in scripts:
			script_s = script.string
			dat_key = "originalImages" if "originalImages" in script_s else 'images'

			lines = script_s.split(";")
			for line in [tmp for tmp in lines if dat_key in tmp]:
				url = line.split("=")[-1]
				url = json.loads(url)
				images.append((img_idx, url))
				img_idx += 1

		self.log.info("Found %s page manga!" % len(images))
		if len(images) < 1:
			self.log.error("No Images on page?")
			return "Failed", ""


		for indice, link in images:
			regx4 = re.compile("http://.+/")
			filename = regx4.sub("" , link)
			filename = filename.rsplit("?")[0]

			filePath = os.path.join(dlPath, filename)
			if not self._checkFileExists(filePath):

				imgdath = self.wg.getpage(link, addlHeaders={'Referer': mangaAddr})							# Request Image

				if imgdath == "Failed":
					self.log.error("cannot get manga page")
					successed = False

				else:
					self.log.info("Successfully got: " + filename)
					#print os.access(imPath, os.W_OK), imPath
					#print "Saving"
					writeErrors = 0
					while writeErrors < 3:
						try:
							with open(filePath, "wb") as fp:
								fp.write(imgdath)
							break
						except:
							self.log.critical(traceback.format_exc())
							writeErrors += 1
					else:
						self.log.critical("Could not save file - %s " % filePath)
						successed = False

					#(self, artist, pageUrl, fqDlPath, seqNum=0):

					self.log.info("Successfully got: " + link)
					# def _updatePreviouslyRetreived(self, artist, pageUrl, fqDlPath, pageDesc="", pageTitle="", seqNum=0)
					self._updatePreviouslyRetreived(artist=artistName, pageUrl=sourceUrl, fqDlPath=filePath, seqNum=indice)

			else:
				self.log.info("%s Exists, skipping..." % filename)



		self.log.info("Total %s " % len(images))
		if successed:
			return "Ignore", None

		else:
			return "Failed", ""


	def _getContentUrlFromPage(self, soupIn):

		pass


	def _extractTitleDescription(self, soupin):

		infoContainer = soupin.find(class_="work-info")
		if infoContainer:
			itemTitle = infoContainer.find("h1", class_="title")
			if itemTitle:
				itemTitle = itemTitle.get_text()
			itemCaption = infoContainer.find("p", class_="caption")
			if itemCaption:
				itemCaption = itemCaption.get_text()
			print("title = ", itemTitle)
			print("caption = ", itemCaption)
		else:
			itemTitle = ""
			itemCaption = ""
		if itemCaption is None:
			itemCaption = ""
		return itemTitle, itemCaption


	def _getSinglePageContent(self, dlPathBase, imageTag, baseSoup, artPageUrl):
		imgurl   = imageTag['data-src']
		imgTitle = imageTag['alt']

		itemTitle, itemCaption = self._extractTitleDescription(baseSoup)



		regx4 = re.compile("http://.+/")				# FileName RE
		fname = regx4.sub("" , imgurl)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.

		self.log.info("			Filename = " + fname)
		self.log.info("			Page Image Title = " + imgTitle)
		self.log.info("			FileURL = " + imgurl)

		filePath = os.path.join(dlPathBase, fname)
		if not self._checkFileExists(filePath):

			imgdath = self.wg.getpage(imgurl, addlHeaders={'Referer': artPageUrl})							# Request Image

			if imgdath == "Failed":
				self.log.info("cannot get image")
				return "Failed", ""
			self.log.info("Successfully got: " + fname)
			# print fname
			try:
				with open(filePath, "wb") as fp:
					fp.write(imgdath)
			except:
				self.log.critical("cannot save image")
				self.log.critical(traceback.print_exc())
				self.log.critical("cannot save image")

				return "Failed", ""

			self.log.info("Successfully got: " + imgurl)
			self.log.info("Saved to path: " + filePath)
			return "Succeeded", filePath, itemCaption, itemTitle
		else:
			self.log.info("Exists, skipping... (path = %s)", filePath)
			return "Exists", filePath, itemCaption, itemTitle

	def _getSinglePageManga(self, dlPathBase, imageTag, baseSoup, artPageUrl):
		imgurl   = imageTag['href']
		imgurl = urllib.parse.urljoin(artPageUrl, imageTag['href'])

		imgTitle = imageTag.img['alt']

		imgpage = self.wg.getSoup(imgurl, addlHeaders={'Referer': artPageUrl})

		if not imgpage.img:
			return "Failed", ""

		imgref = imgurl
		imgurl = imgpage.img['src']

		itemTitle, itemCaption = self._extractTitleDescription(baseSoup)

		regx4 = re.compile("https?://.+/")				# FileName RE
		fname = regx4.sub("" , imgurl)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.

		self.log.info("			Filename = " + fname)
		self.log.info("			Page Image Title = " + imgTitle)
		self.log.info("			FileURL = " + imgurl)

		filePath = os.path.join(dlPathBase, fname)
		if not self._checkFileExists(filePath):

			imgdath = self.wg.getpage(imgurl, addlHeaders={'Referer': imgref})							# Request Image

			if imgdath == "Failed":
				self.log.info("cannot get image")
				return "Failed", ""
			self.log.info("Successfully got: " + fname)
			# print fname
			try:
				with open(filePath, "wb") as fp:
					fp.write(imgdath)
			except:
				self.log.critical("cannot save image")
				self.log.critical(traceback.print_exc())
				self.log.critical("cannot save image")

				return "Failed", ""

			self.log.info("Successfully got: " + imgurl)
			self.log.info("Saved to path: " + filePath)
			return "Succeeded", filePath, itemCaption, itemTitle
		else:
			self.log.info("Exists, skipping... (path = %s)", filePath)
			return "Exists", filePath, itemCaption, itemTitle

	def _getAnimation(self, dlPathBase, imageTag, soup, artPageUrl):
		itemTitle, itemCaption = self._extractTitleDescription(soup)

		scripts = soup.find("script", text=re.compile("ugokuIllustFullscreenData"))
		if not scripts:
			return "Failed", ""

		script = scripts.string
		lines = script.split(";")

		tgtline = ""
		for line in lines:
			if "pixiv.context.ugokuIllustFullscreenData" in line and "=" in line:
				tgtline = line

		if not tgtline:
			return "Failed", ""

		dat = json.loads(tgtline.split("=")[-1])
		itemCaption += "\n\n<pre>" + tgtline + "</pre>"

		if not 'src' in dat:
			return "Failed", ""

		ctntsrc = dat['src']

		regx4 = re.compile("https?://.+/")				# FileName RE
		fname = regx4.sub("" , ctntsrc)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.

		self.log.info("			Filename = " + fname)
		self.log.info("			Page Image Title = " + itemTitle)
		self.log.info("			FileURL = " + ctntsrc)

		filePath = os.path.join(dlPathBase, fname)
		if not self._checkFileExists(filePath):

			imgdath = self.wg.getpage(ctntsrc, addlHeaders={'Referer': artPageUrl})							# Request Image

			if imgdath == "Failed":
				self.log.info("cannot get image")
				return "Failed", ""
			self.log.info("Successfully got: " + fname)
			# print fname
			try:
				with open(filePath, "wb") as fp:
					fp.write(imgdath)
			except:
				self.log.critical("cannot save image")
				self.log.critical(traceback.print_exc())
				self.log.critical("cannot save image")

				return "Failed", ""

			self.log.info("Successfully got: " + ctntsrc)
			self.log.info("Saved to path: " + filePath)
			return "Succeeded", filePath, itemCaption, itemTitle
		else:
			self.log.info("Exists, skipping... (path = %s)", filePath)
			return "Exists", filePath, itemCaption, itemTitle


	def _getArtPage(self, dlPathBase, pgurl, artistName):

		'''
		Pixiv does a whole lot of referrer sniffing. They block images, and do page redirects if you don't submit the correct referrer.
		Also, I *think* they will block flooding, so that's the reason for the delays everywhere.
		'''

		baseSoup = self.wg.getSoup(pgurl)


		imageTag = baseSoup.find('img', class_="original-image")
		if imageTag:
			return self._getSinglePageContent(dlPathBase, imageTag, baseSoup, pgurl)

		work_div = baseSoup.find("div", class_='works_display')
		if work_div:

			mangaContent = work_div.find("a", class_='multiple')
			if mangaContent:
				link = urllib.parse.urljoin(pgurl, mangaContent['href'])
				self.log.info("Multipage/Manga link")
				return self.getManga(artistName, link, dlPathBase, baseSoup, pgurl)

			singleManga = work_div.find("a", class_='manga')
			if singleManga:
				return self._getSinglePageManga(dlPathBase, singleManga, baseSoup, pgurl)
			animation = work_div.find("div", class_='_ugoku-illust-player-container')
			if animation:
				return self._getAnimation(dlPathBase, animation, baseSoup, pgurl)

		raise RuntimeError("Unknown content type!")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://www.pixiv.net/member_illust.php?id=%s" % artist
		page = self.wg.getSoup(basePage)

		mainDiv = page.find("div", class_="layout-a")
		if not mainDiv:
			raise LookupError("Could not retreive artist item quantity!")
		countSpan = mainDiv.find("span", class_="count-badge")
		if not countSpan:
			raise LookupError("Could not retreive artist item quantity!")

		text = countSpan.text.split()[0]
		text = ''.join([char for char in text if char in '0123456789'])
		return int(text)


	def _getItemsOnPage(self, inSoup):

		links = set()

		imgItems = inSoup.find_all("li", class_="image-item")
		for tag in imgItems:
			url = urllib.parse.urljoin(self.urlBase, tag.a["href"])
			links.add(url)

		return links


	def _getGalleries(self, artist):


		# re string is "該当ユーザーのアカウントは停止されています。" escaped, so the encoding does not mangle it.
		# It translates to "This account has been suspended"
		suspendedAcctRe = re.compile("\xe8\xa9\xb2\xe5\xbd\x93\xe3\x83\xa6\xe3\x83\xbc\xe3\x82\xb6\xe3\x83\xbc\xe3\x81\xae\xe3\x82\xa2\xe3" +
			"\x82\xab\xe3\x82\xa6\xe3\x83\xb3\xe3\x83\x88\xe3\x81\xaf\xe5\x81\x9c\xe6\xad\xa2\xe3\x81\x95\xe3\x82\x8c\xe3\x81\xa6\xe3\x81\x84\xe3\x81\xbe\xe3\x81\x99\xe3\x80\x82")


		iterCounter = 0


		artlinks = set()

		while 1:
			turl = "http://www.pixiv.net/member_illust.php?id=%s&p=%s" % (artist, iterCounter+1)
			self.log.info("Getting = " + turl)
			mpgctnt = self.wg.getpage(turl)
			if mpgctnt == "Failed":
				self.log.info("Cannot get Page")
				return set()
			if suspendedAcctRe.search(mpgctnt):
				self.log.critical("Account has been suspended. You should probably remove it from your favorites")
				self.log.critical("Account # %s" % artist)
				self.log.critical("Gallery URL - %s" % turl)
				return set()

			soup = bs4.BeautifulSoup(mpgctnt, 'lxml')
			new = self._getItemsOnPage(soup)
			new = new - artlinks

			if not len(new) or not flags.run:
				break

			artlinks |= new

			if iterCounter > 500:
				self.log.critical("This account seems to have too many images, or is defunct.")
				self.log.critical("Account: %s" % artist)

				artlinks = set()
				break

			iterCounter += 1

		self.log.info("Found %s links" % (len(artlinks)))


		if ((iterCounter * 20) - len(artlinks)) > 20:
			self.log.warning("We seem to have found less than 20 links per page. are there missing files?")
			self.log.warning("Found %s links on %s pages. Should have found %s - %s links" % (len(artlinks), iterCounter, (iterCounter - 1) * 20, iterCounter * 20))

		return artlinks



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):
		self.checkLogin()

		self.log.info("Getting list of favourite artists.")

		breakFlag = True
		counter = 1
		content = ""
		resultList = set()
		nameRE = re.compile(r'<a href="member\.php\?id=(\d*?)"')

		while 1:
			breakFlag = True
			pageURL = "http://www.pixiv.net/bookmark.php?type=user&rest=show&p=%d" % (counter)
			content = self.wg.getpage(pageURL)
			if content == "Failed":
				self.log.info("cannot get image")
				return "Failed"

			temp = nameRE.findall(content)
			new = set(temp)
			new = new - resultList

			counter += 1


			if not len(new) or not flags.run:			# Break when none of the new names were original
				break

			resultList |= new

			self.log.info("Names found so far - %s", len(resultList))

		self.log.info("Found %d Names" % len(resultList))

		return resultList
