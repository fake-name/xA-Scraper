
import os
import os.path
import traceback
import dateparser
import re
import bs4
import urllib.request
import urllib.parse
from settings import settings
import flags

import util.unclassify

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class GetIB(xascraper.modules.scraper_base.ScraperBase):

	settingsDictKey = "ib"

	pluginName = "IbGet"

	urlBase = "https://inkbunny.net/"


	ovwMode = "Check Files"

	numThreads = 2



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):


		pagetext = self.wg.getpage(self.urlBase)
		if settings["ib"]["username"] in pagetext:
			return True, "Have ib Cookie."
		else:
			return False, "Do not have ib login Cookies"


	def getToken(self):
			self.log.info("Getting Entrance Cookie")
			soup = self.wg.getSoup('https://inkbunny.net/login.php')
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
				# print("accessToken", accessToken)

				logondict = {"token"        : accessToken,
							"username"      : settings["ib"]["username"],
							"password"      : settings["ib"]["password"]
							}

				extraHeaders = {
							"Referer"       : "https://inkbunny.net/login.php",
				}

				pagetext = self.wg.getpage('https://inkbunny.net/login_process.php', postData=logondict, addlHeaders=extraHeaders)
				with open('temp.html', 'w') as fp:
					fp.write(pagetext)
				if settings["ib"]["username"] in pagetext:

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




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _fetchImage(self, imageURL, dlPathBase, itemCaption, itemTitle, artPageUrl):
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
			return filePath
		else:
			imgdat = self.wg.getpage(imageURL, addlHeaders={'Referer':artPageUrl})


			# For text, the URL fetcher returns decoded strings, rather then bytes.
			# Therefore, if the file is a string type, we encode it with utf-8
			# so we can write it to a file.
			if isinstance(imgdat, str):
				imgdat = imgdat.encode(encoding='UTF-8')

			filePath = self.save_file(filePath, imgdat)
			if not filePath:
				return self.build_page_ret(status="Failed", fqDlPath=None)

			self.log.info("Successfully got: %s", imageURL)

		return filePath

	def _getContentUrlFromPage(self, soup=None, url=None):
		if not soup:
			soup = self.wg.getSoup(url)

		resize       = soup.find('div', title='Click to show max preview size')
		origSize     = soup.find_all('a', target='_blank')
		swfContainer = soup.find('embed', type='application/x-shockwave-flash')

		origSize = list(set([tmp['href'] for tmp in origSize if tmp.get('href') and '/full/' in tmp.get('href')]))
		if len(origSize) > 1:
			self.log.error("Too many content images? Wat?")
			self.log.error("%s", origSize)
		elif not origSize:
			ctnt_l = soup.select("div.content.magicboxParent")
			for ctnt in ctnt_l:

				if ctnt and ctnt.img and ctnt:
					for img in ctnt.find_all("img"):
						if "/full/" in img['src']:
							origSize = [img['src']]
				if origSize:
					break
				if not origSize and ctnt:
					links = ctnt.find_all("a")
					for link in links:
						if "/full/" in link['href']:
							origSize = [link['href']]
				if origSize:
					break
			if not origSize:
				self.log.error("No image on page?")
				self.log.error("%s", origSize)

		if resize:
			# print("Resize link found:", resize.a['href'])
			return resize.a['href']
		elif origSize:
			# print("OrigSize valid:", origSize)
			return origSize[0]
		elif swfContainer:
			# print("SwfContainer found: ", swfContainer)
			return swfContainer['src']
		else:
			self.log.error("No content found on page!")
			# print("Nothing found?")
			return None



	def _extractTitle(self, soup):
		div = soup.find('div', class_='content')
		tds = div.find_all('td')
		if len(tds) == 4:
			dummy_avatar, titleTd, dummy_smiley, dummy_donate = tds
		elif len(tds) == 2:
			dummy_avatar, titleTd = tds
		elif len(tds) == 6:
			dummy_prev_release, dummy_author_1, dummy_author_2, dummy_avatar, titleTd, dummy_next_release = tds
		else:
			print("TDS:", len(tds))
			for td in tds:
				print()
				print("----------------------------------------")
				print(td)
				print("----------------------------------------")
				print()
			raise ValueError("Do not know how to unpack title!")

		if len(tds) == 6:
			return titleTd.get_text()
		else:
			title, dummy_by = titleTd.find_all('div')
			return title.get_text().strip()


	def _extractDescription(self, story_div, desc_soup, tag_soup):
		desc = bs4.BeautifulSoup('', "lxml").new_tag('div')

		if story_div:
			story = story_div.find("div", id='storysectionbar')
			story = util.unclassify.unclassify(story.extract())
			desc.append(story)


		# Tag extraction has to go before description extraction, because
		# the desc extraction modifies the tree
		kwdHeader = tag_soup.find('div', id='kw_scroll')
		tags = kwdHeader.next_sibling.next_sibling

		# Horrible hack using ** to work around the fact that 'class' is a reserved keyword
		tagDiv = bs4.BeautifulSoup('', "lxml").new_tag('div', **{'class' : 'tags'})

		tagHeader = bs4.BeautifulSoup('', "lxml").new_tag('b')
		tagHeader.append('Tags:')
		tagDiv.append(tagHeader)

		for tag in tags.find_all('a'):
			if 'block by ' in tag.get_text():
				continue
			new = bs4.BeautifulSoup('', "lxml").new_tag('div', **{'class' : 'tag'})
			tagtxt = tag.get_text().strip()
			if tagtxt != "keywording policy":
				new.append(tagtxt)
				tagDiv.append(new)


		div = desc_soup.find('div', class_='content')
		div = util.unclassify.unclassify(div)



		if div.div.span:
			desc.append(div.div.span)
		else:
			desc.append(div)

		desc.append(tagDiv)
		desc = str(desc.prettify())
		return desc.strip()

	def _extractPostTimestamp(self, soup):
		datespan = soup.find('span', id='submittime_exact')
		datetxt = datespan.get_text()
		postts = dateparser.parse(datetxt).replace(tzinfo=None)
		return postts

	def _extractPostTags(self, soup):
		tagdiv = soup.find('div', id='kw_scroll')
		taglinks = tagdiv.parent.find_all("a", href=re.compile(r"search_process\.php\?keyword_id"))
		tags = [tag.span.get_text().strip() for tag in taglinks]
		return tags

	def _getSeqImageDivs(self, seqDiv):
		ret = set()

		pages = seqDiv.find_all('div', class_='widget_imageFromSubmission')

		for page in pages:
			pgUrl = urllib.parse.urljoin(self.urlBase, page.a['href'])
			ctnt = self._getContentUrlFromPage(url=pgUrl)
			if ctnt:
				ret.add(ctnt)
		return ret

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		soup = self.wg.getSoup(artPageUrl)
		soups = str(soup)
		if 'ERROR: That submission has been deleted.' in soups:
			self.log.warning("Item %s has been deleted by the poster!", artPageUrl)
			return self.build_page_ret(status="Deleted", fqDlPath=None)

		if 'The owner has restricted this submission to members' in soups:
			raise exceptions.NotLoggedInException("Not logged in?")
		if "You may need to go to that member's userpage (use name link above) and request that they give you access" in soups:
			raise exceptions.CannotAccessException("Friends only thingie (why is this even a thing)!")

		postTime    = self._extractPostTimestamp(soup)
		postTags    = self._extractPostTags(soup)

		titleBar, dummy_stats, dummy_footer = soup.body.find_all('div', class_='elephant_555753', recursive=False)

		story_div = None

		mainDivs = soup.body.find_all('div', class_='elephant_white', recursive=False)
		if len(mainDivs) == 2:
			imgDiv, desc_div = mainDivs
			footer = desc_div
			imageURL    = [self._getContentUrlFromPage(imgDiv)]
		elif len(mainDivs) == 3 or len(mainDivs) == 4:
			if len(mainDivs) == 3:
				imgDiv, seqDiv, desc_div = mainDivs
				footer = desc_div
			if len(mainDivs) == 4:
				imgDiv, seqDiv, desc_div, footer = mainDivs

			imageURL = set()
			base_img = self._getContentUrlFromPage(imgDiv)
			if base_img:
				imageURL.add(base_img)

			for img in self._getSeqImageDivs(seqDiv):
				# print("Adding: ", img)
				imageURL.add(img)
			for img in self._getSeqImageDivs(desc_div):
				# print("Adding: ", img)
				imageURL.add(img)
			self.log.info("Found %s item series on page!", len(imageURL))

		elif len(mainDivs) == 5:
			header_div, img_div, story_div, desc_div, footer = mainDivs


			imageURL = set()
			base_img = self._getContentUrlFromPage(img_div)
			if base_img:
				imageURL.add(base_img)

			for img in self._getSeqImageDivs(desc_div):
				# print("Adding: ", img)
				imageURL.add(img)
			self.log.info("Found %s item series on page!", len(imageURL))
		else:
			soupp = str(mainDivs)
			with open("log.html", "w") as fp:
				fp.write(soupp)
			print(soupp)

			raise ValueError("Unknown number of mainDivs! %s" % len(mainDivs))

		# print(imageURL)

		itemTitle   = self._extractTitle(titleBar)
		itemCaption = self._extractDescription(story_div, desc_div, footer)

		if not imageURL:
			self.log.error("OH NOES!!! No image on page = " + artPageUrl)
			return self.build_page_ret(status="Failed", fqDlPath=None)


		imPaths = []
		for image in imageURL:
			recPath = self._fetchImage(image, dlPathBase, itemCaption, itemTitle, artPageUrl)
			imPaths.append(recPath)

		return self.build_page_ret(status="Succeeded", fqDlPath=imPaths, pageDesc=itemCaption, pageTitle=itemTitle, postTags=postTags, postTime=postTime)

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):

		basePage = 'https://inkbunny.net/{user}'.format(user=artist)

		page = self.wg.getSoup(basePage)
		stats = page.find('span', class_='stat', title='Submissions Uploaded')
		if stats and stats.strong:
			return int(stats.strong.get_text().replace(",", ""))

		raise exceptions.AccountDisabledException("Could not retreive artist item quantity!")



	def _getItemsOnPage(self, inSoup):

		links = set()

		pages = inSoup.find_all("div", class_='widget_thumbnailLargeCompleteFromSubmission')
		for page in pages:
			itemUrl = urllib.parse.urljoin(self.urlBase, page.a['href'])
			links.add(itemUrl)

		nextPage = False
		button = inSoup.find("span", text='Next Page')
		if button:
			url = button.parent['href']
			nextPage = urllib.parse.urljoin(self.urlBase, url)

		return links, nextPage

	def _getGalleryUrls(self, baseUrl):

		pageSoup = self.wg.getSoup(baseUrl)

		baseGal   = pageSoup.find('a', text='Gallery')
		scrapsGal = pageSoup.find('a', text='Scraps')
		csGal     = pageSoup.find('a', text='Character Sheets')

		ret = []
		if baseGal:
			ret.append(urllib.parse.urljoin(baseUrl, baseGal['href']))
		if scrapsGal:
			ret.append(urllib.parse.urljoin(baseUrl, scrapsGal['href']))
		if csGal:
			ret.append(urllib.parse.urljoin(baseUrl, csGal['href']))
		return ret

	def _getItemsFromGallery(self, nextUrl):
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

		baseUrl = 'https://inkbunny.net/{user}'.format(user=artist)
		galleries = self._getGalleryUrls(baseUrl)

		artlinks = set()
		for gal in galleries:
			artlinks |= self._getItemsFromGallery(gal)

		self.log.info("Found %s links" % (len(artlinks)))
		return artlinks





if __name__ == '__main__':
	import multiprocessing.managers
	import logSetup

	logSetup.initLogging()


	manager = multiprocessing.managers.SyncManager()
	manager.start()
	namespace = manager.Namespace()
	namespace.run=True


	ins = GetIB()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	print("Getting artist")
	# ins.getCookie()
	# ins._getArtPage("xxxx", 'https://inkbunny.net/submissionview.php?id=xxx', 'testtt')

