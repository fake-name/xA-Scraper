
import os
import os.path
import traceback
import re
import bs4
import urllib.request
import urllib.parse
from settings import settings
import flags

import plugins.scrapers.ScraperBase

class GetWy(plugins.scrapers.ScraperBase.ScraperBase):

	settingsDictKey = "wy"

	pluginName = "WyGet"

	urlBase = "https://www.weasyl.com/"


	ovwMode = "Check Files"

	numThreads = 1



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):


		pagetext = self.wg.getpage('https://www.weasyl.com/')
		if settings["wy"]["username"] in pagetext:
			return True, "Have Wy Cookie."
		else:
			return False, "Do not have Wy login Cookies"


	def getToken(self):
			self.log.info("Getting Entrance Cookie")
			soup = self.wg.getSoup('https://www.weasyl.com/signin')
			inputs = soup.find_all("input")

			for intag in inputs:
				if 'name' in intag.attrs and intag['name'] == 'token':
					return intag['value']

			return False

	def getCookie(self):
		try:

			accessToken = self.getToken()

			#print soup.find_all("input")
			#print soup
			if accessToken:
				self.log.info("Got Entrance token, logging in")
				print("accessToken", accessToken)

				logondict = {"token"        : accessToken,
							"username"      : settings["wy"]["username"],
							"password"      : settings["wy"]["password"],
							"Referer"       : "https://www.weasyl.com/"}

				extraHeaders = {
							"Referer"       : "https://www.weasyl.com/signin",
				}

				pagetext = self.wg.getpage('https://www.weasyl.com/signin', postData=logondict, addlHeaders=extraHeaders)
				if settings["wy"]["username"] in pagetext:

					self.wg.saveCookies()
					return True, "Logged In"
				else:
					self.log.error("Login failed!")
					return False, "Failed to log in"
			return "No hidden input - entry step-through failed"

		except:
			self.log.critical("Caught Error")
			self.log.critical(traceback.format_exc())
			traceback.print_exc()
			return "Login Failed"




	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromPage(self, soup):

		dlBar = soup.find('ul', id='detail-actions')


		dummy, dlLink, dummy = dlBar.find_all('li')
		if 'Download' in dlLink.get_text():
			itemUrl = urllib.parse.urljoin(self.urlBase, dlLink.a['href'])

			return itemUrl

		raise ValueError("Wat?")

	def _extractTitleDescription(self, soup):
		title = soup.find('h2', id='detail-bar-title')
		title = title.get_text().strip()

		descContainer = soup.find('div', id='detail-description')
		desc = descContainer.find('div', class_='formatted-content')

		tags = soup.find('div', class_='di-tags')

		# Horrible hack using ** to work around the fact that 'class' is a reserved keyword
		tagDiv = soup.new_tag('div', **{'class' : 'tags'})

		tagHeader = soup.new_tag('b')
		tagHeader.append('Tags:')
		tagDiv.append(tagHeader)

		for tag in tags.find_all('a'):
			new = soup.new_tag('div', **{'class' : 'tag'})
			new.append(tag.get_text())
			tagDiv.append(new)

		desc.append(tagDiv)
		desc = str(desc.prettify())
		return title, desc

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		soup = self.wg.getSoup(artPageUrl)


		imageURL = self._getContentUrlFromPage(soup)
		itemTitle, itemCaption = self._extractTitleDescription(soup)

		if not imageURL:
			self.log.error("OH NOES!!! No image on page = " + artPageUrl)
			raise ValueError("No image found!")

		urlPath = urllib.parse.urlparse(imageURL).path
		fName = urlPath.split("/")[-1]

		if not fName:
			self.log.error("OH NOES!!! No filename for image on page = " + artPageUrl)
			raise ValueError("No filename found!")


		filePath = os.path.join(dlPathBase, fName)

		self.log.info("			Filename			= %s", fName)
		self.log.info("			Page Image Title	= %s", itemTitle)
		self.log.info("			FileURL				= %s", imageURL)
		self.log.info("			dlPath				= %s", filePath)

		if self._checkFileExists(filePath):
			self.log.info("Exists, skipping...")
			return "Exists", filePath, itemCaption, itemTitle
		else:
			imgdat = self.wg.getpage(imageURL, addlHeaders={'Referer':artPageUrl})

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
						return "Failed", ""



			self.log.info("Successfully got: %s" % imageURL)
			return "Succeeded", filePath, itemCaption, itemTitle

	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		# Apparently users can turn this off? Fucking annoying.

		basePage = "https://www.weasyl.com/~{user}".format(user=artist)

		page = self.wg.getSoup(basePage)
		stats = page.find('div', id='user-stats')
		if not stats:
			return None

		item = stats.find("dd", text='Submissions')
		if not item:
			return None

		if item:
			# This feels a bit brittle, but I can't see how else to get the row
			# I want.
			items = item.previous_sibling.previous_sibling.get_text()
			return int(items)

		raise LookupError("Could not retreive artist item quantity!")



	def _getItemsOnPage(self, inSoup):

		links = set()
		itemUl = inSoup.find("ul", class_='thumbnail-grid')
		if not itemUl:
			return [], False
		pages = itemUl.find_all("li", class_='item')
		for page in pages:
			itemUrl = urllib.parse.urljoin(self.urlBase, page.a['href'])
			links.add(itemUrl)

		nextPage = False
		buttons = inSoup.find_all("a", class_='button')
		for link in buttons:
			if 'next' in link.get_text().lower():
				nextPage = urllib.parse.urljoin(self.urlBase, link['href'])

		return links, nextPage

	def _getDirectories(self, baseUrl):

		pageSoup = self.wg.getSoup(baseUrl)
		dirDiv = pageSoup.find('div', class_='sectioned-sidebar')
		if not dirDiv:
			return []
		assert dirDiv.h3.get_text() == 'Folders'

		links = []

		for link in dirDiv('a'):
			item = urllib.parse.urljoin(self.urlBase, link['href'])
			links.append(item)

		return links



	def _getItemsInDir(self, nextUrl):
		ret = set()
		while nextUrl:

			if not flags.run:
				break

			self.log.info("Getting = '%s'", nextUrl)
			pageSoup = self.wg.getSoup(nextUrl)
			if pageSoup == False:
				self.log.error("Cannot get Page")
				return "Failed"

			new, nextUrl = self._getItemsOnPage(pageSoup)
			new = new - ret
			self.log.info("Retrieved %s new items on page", len(new))
			ret |= new
		return ret


	def _getGalleries(self, artist):

		artlinks = set()
		artist = artist.strip()

		baseUrl = 'https://www.weasyl.com/submissions/{user}'.format(user=artist)
		dirs = self._getDirectories(baseUrl)
		dirs.append(baseUrl)

		for url in dirs:
			artlinks |= self._getItemsInDir(url)

		self.log.info("Found %s links" % (len(artlinks)))
		return artlinks



