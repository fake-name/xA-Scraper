
import os
import os.path
import traceback
import re
import bs4
import dateparser
import urllib.request
import urllib.parse
from settings import settings
import flags

import rewrite.modules.scraper_base
from rewrite.modules import exceptions

class GetHF(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "hf"

	pluginName = "HfGet"

	urlBase = "www.hentai-foundry.com"


	ovwMode = "Check Files"

	numThreads = 2



	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		self.log.info("HF Checking cookies")
		YII_CSRF_TOKEN = re.search(r"<Cookie YII_CSRF_TOKEN=[\w%]*? for www\.hentai-foundry\.com\/>", "%s" % self.wg.cj)
		PHPSESSID = re.search(r"<Cookie PHPSESSID=[\w%]*? for www\.hentai-foundry\.com\/>", "%s" % self.wg.cj)

		if YII_CSRF_TOKEN and PHPSESSID:
			return True, "Have HF Cookies:\n	%s\n	%s" % (YII_CSRF_TOKEN.group(0), PHPSESSID.group(0))

		return False, "Do not have HF login Cookies"

	def stepThroughEntry(self):
			self.log.info("Getting Entrance Cookie")
			ctnt = self.wg.getpage('http://www.hentai-foundry.com/site/login?enterAgree=1&size=728')

			soup = bs4.BeautifulSoup(''.join(ctnt), 'lxml')
			hiddenInput = soup.find('input', attrs={"name" : "YII_CSRF_TOKEN"})
			# print "ctnt = ", ctnt

			if soup.find("label", attrs={"for" : "LoginForm_verifyCode"}):
				print("Need to enter captcha")

				print(soup.find("img", id="yw1"))
				#cookiesupport.cookiePrompt(img, parent)

				self.log.error("Entry Login Failed!")
				raise ValueError("Please log in manually")

			return hiddenInput

	def getCookie(self):
		self.log.info("HF Getting cookie")
		try:

			hiddenInput = self.stepThroughEntry()
			#print soup.find_all("input")
			#print soup
			if hiddenInput:
				self.log.info("Got Entrance Cookie, logging in")
				YII_CSRF_TOKEN = hiddenInput["value"]


				logondict = {"YII_CSRF_TOKEN"       : YII_CSRF_TOKEN,
							"LoginForm[rememberMe]" : "1",
							"LoginForm[username]"   : settings["hf"]["username"],
							"LoginForm[password]"   : settings["hf"]["password"],
							"Referer"               : "http://www.hentai-foundry.com/site/login"}

				pagetext = self.wg.getpage('http://www.hentai-foundry.com/site/login', postData = logondict)
				if not "Incorrect username or password." in pagetext:
					self.wg.saveCookies()
					return True, "Logged In"
				else:
					return False, "Failed to log in"
			return "No hidden input - entry step-through failed"

		except:
			self.log.critical("Caught Error")
			traceback.print_exc()
			return "Login Failed"




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromPage(self, soupIn):

		# TODO: Proper page parsing, rather then regexes


		contentDiv = soupIn.find('div', attrs={"class" : "container", "id" : "page"})			# Image should be in the first <div>
		boxDiv = contentDiv.findNext("div", class_="boxbody")
		imgLink = boxDiv.findNext("img")


		if imgLink:
			# Content is hosted on the  pictures.hentai-fountry.net subdomain. Therefore, we want to validate that
			if "//pictures." in imgLink.get("src", ""):
				imageURL = imgLink["src"]
				self.log.info("%s%s" % ("Found Image URL : ", imageURL))
				return imageURL

			if "//pictures." in imgLink.get("onclick", ""):
				# This is untested. I'm not sure how the decision making for
				# whether to serve the resized image works, and I can't seem to get
				# it to serve the smaller images to my script.
				onclick = imgLink.get("onclick", "")
				extractre = re.compile(r"this\.src=\'(//pictures\..*?)\';", re.IGNORECASE)
				res = extractre.search(onclick)
				if res:
					return res.group(1)


		flashContent = boxDiv.findNext("param", attrs={"name" : "movie"})
		if flashContent:
			imageURL = flashContent.findNext("embed")["src"]
			self.log.info("%s%s" % ("Found Flash URL : ", imageURL))
			return imageURL




		subPageLink = boxDiv.findNext("a")

		if subPageLink:

			tempLink = urllib.parse.urljoin("http://www.hentai-foundry.com/", subPageLink["href"])

			redirLinkFound = False

			self.log.info("Image is on a sub-Page; Fetching sub page")
			pgSoup = self.wg.getSoup(tempLink)					# Get Webpage

			if pgSoup != "Failed":

				imgLink = pgSoup.find('div', attrs={"class" : "box"}).findNext("div", attrs={"class" : "boxbody"}).findNext("img")

				if imgLink:
					if imgLink["src"].find("pictures") + 1:			# Content is hosted on the  pictures.hentai-fountry.net subdomain. Therefore, we want the


						imageURL = imgLink["src"]

						redirLinkFound = True
						self.log.info("%s%s" % ("Found Image URL : ", imageURL))

						return imageURL

			if not redirLinkFound:
				self.log.error("Failed to retreive image!")

		return False

	def _extractTitleDescription(self, soup):

		itemTitle = ""
		itemCaption = ""

		itemTitle = soup.find("span", class_="imageTitle")
		itemTitle = itemTitle.get_text()

		itemCaptionDiv = soup.find("div", class_="picDescript")
		itemCaption = itemCaptionDiv.extract()

		# Horrible hack using ** to work around the fact that 'class' is a reserved keyword
		tagDiv = soup.new_tag('div', **{'class' : 'tags'})

		tagHeader = soup.new_tag('b')
		tagHeader.append('Tags:')
		tagDiv.append(tagHeader)

		tags = soup.find('div', id='submission_tags')
		tags = [tag.get_text().strip() for tag in soup.find_all('a', rel='tag')]
		tags = set(tags)
		for tag in tags:
			new = soup.new_tag('div', **{'class' : 'tag'})
			new.append(tag)
			tagDiv.append(new)

		itemCaption.append(tagDiv)

		itemCaption = itemCaption.prettify()


		metadiv = soup.find("section", id='yw0')
		posttime = metadiv.time['datetime']
		print("Unparsed posttime:", posttime)
		posttime = dateparser.parse(posttime)
		print("Parsed posttime:", posttime)
		self.log.info("Image tags: %s", list(tags))
		self.log.info("Image Posted: %s", posttime)

		return itemTitle, itemCaption, tags, posttime.replace(tzinfo=None)

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):


		pgSoup = self.wg.getSoup(artPageUrl)					# Get Webpage

		if pgSoup == "Failed":
			self.log.error("cannot get page")
			return self.build_page_ret(status="Failed", fqDlPath=None)


		imageURL = self._getContentUrlFromPage(pgSoup)
		imgTitle, itemCaption, postTags, postTime = self._extractTitleDescription(pgSoup)

		if not imageURL:
			self.log.error("OH NOES!!! No image on page = " + artPageUrl)
			return self.build_page_ret(status="Failed", fqDlPath=None)										# Return Fail



		if "http" not in imageURL.lower():
			imageURL =  urllib.parse.urljoin("http://hentai-foundry.com", imageURL)

		fTypeRegx	= re.compile(r"http://.+?\.com.*/.*?\.")
		fNameRegex	= re.compile(r"http://.+/")
		ftype		= fTypeRegx.sub("" , imageURL)
		fname		= fNameRegex.sub("" , imageURL)

		if ftype == imageURL:								# If someone forgot the filename it may not be a .jpg, but it's likely any image viewer can figure out what it is.
			fname += ".jpg"


		if imgTitle != None:
			fname = "%s.%s" % (re.sub(r'[^a-zA-Z0-9\-_.() ]', '', imgTitle), fname)

		filePath = os.path.join(dlPathBase, fname)

		self.log.info("			Filename			= %s", fname)
		self.log.info("			Page Image Title		= %s", imgTitle)
		self.log.info("			FileURL				= %s", imageURL)
		self.log.info("			FileType			= %s", ftype)
		self.log.info("			dlPath				= %s", filePath)

		if self._checkFileExists(filePath):
			self.log.info("Exists, skipping...")
			return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=imgTitle, postTags=postTags, postTime=postTime)
		else:
			imgdat = self.wg.getpage(imageURL)							# Request Image

			if imgdat == "Failed":
				self.log.error("cannot get image")
				return self.build_page_ret(status="Failed", fqDlPath=None)



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
					fp.write(imgdat)						# Write Image to File
					fp.close()
				except IOError:
					try:
						fp.close()
					except:
						pass
					errs += 1
					self.log.critical("Error attempting to save image file - %s", filePath)
					if errs > 3:
						self.log.critical("Could not open file for writing!")
						return self.build_page_ret(status="Failed", fqDlPath=None)



			self.log.info("Successfully got: %s", imageURL)
			return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=imgTitle, postTags=postTags, postTime=postTime)

		raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "http://www.hentai-foundry.com/user/%s/profile" % artist
		page = self.wg.getSoup(basePage)

		tds = page.find("b", text="# Pictures")

		stats = tds.parent.parent.find("td", text=re.compile(r"^\d+$"))
		if stats:
			return int(stats.text)

		raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")


	def _getItemsOnPage(self, inSoup):

		links = set()

		imageLinks = inSoup.find_all('span', class_="thumb")

		for imageLink in imageLinks:

			try:
				link = imageLink.find_parent()["href"]
				fullLink = urllib.parse.urljoin("http://www.hentai-foundry.com/", link)			 # Extract link
			except KeyError:										# badly formed link ? probably just a named anchor like '<a name="something">'
				continue

			links.add(fullLink)

		return links


	def _getGalleries(self, artist):


		artlinks = set()

		artist = artist.strip()

		subGalleries = ["http://www.hentai-foundry.com/pictures/user/%s/page/%s",
					"http://www.hentai-foundry.com/pictures/user/%s/scraps/page/%s"]

		for gallery in subGalleries:
			pageNumber = 1
			while 1:

				if not flags.run:
					break

				turl = gallery % (artist, pageNumber)
				pageNumber += 1

				self.log.info("Getting = " + turl)
				pageSoup = self.wg.getSoup(turl)
				if pageSoup is False:
					self.log.error("Cannot get Page")
					return "Failed"

				new = self._getItemsOnPage(pageSoup)
				new = new - artlinks
				self.log.info("Retrieved %s new items on page", len(new))
				artlinks |= new

				if not len(new):
					break

		self.log.info("Found %s links" % (len(artlinks)))
		return artlinks



if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	ins = GetHF()
	# ins.getCookie()
	# print(ins)
	# print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	ins._getArtPage("xxxx", 'xxxx', 'testtt')

