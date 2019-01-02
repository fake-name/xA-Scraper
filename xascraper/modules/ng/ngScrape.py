
import os
import os.path
import traceback
import bs4
import dateparser
import urllib.request
import urllib.parse
from settings import settings
import flags

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class GetNg(xascraper.modules.scraper_base.ScraperBase):

	settingsDictKey = "ng"

	pluginName = "NgGet"

	urlBase = "https://www.newgrounds.com/"

	ovwMode = "Check Files"

	numThreads = 1


	def __init__(self):
		super().__init__()

		# So newgrounds is really flaky about serving content sometimes, not sure why.
		# Anways, turn up the retries (and the delay on failure) because of that.
		self.wg.retryDelay = 15
		self.wg.errorOutCount  = 3

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):


		pagetext = self.wg.getpage(self.urlBase)
		if settings["ng"]["username"] in pagetext:
			return True, "Have Ng Cookie."
		else:
			return False, "Do not have Ng login Cookies"


	def get_target(self):
			self.log.info("Getting Entrance Cookie")
			soup = self.wg.getSoup(self.urlBase)
			if '/passport/mode/iframe' not in soup:
				self.log.warning("No login iframe? Maybe logged in?")
				return False
			soup = self.wg.getSoup('https://www.newgrounds.com/passport/mode/iframe', addlHeaders={'referer':self.urlBase})
			form = soup.find("form")

			action_target = form.get("action", False)
			if action_target:
				return urllib.parse.urljoin(self.urlBase, action_target)

			return False

	def getCookie(self):
		try:

			action_target = self.get_target()
			print("Action target:", action_target)
			#print soup.find_all("input")
			#print soup
			if action_target:
				self.log.info("Got Entrance url, logging in")

				logondict = {
							"login"        : "1",
							"remember"        : "1",
							"username"      : settings["ng"]["username"],
							"password"      : settings["ng"]["password"],
							}

				extraHeaders = {
							"referer"       : "https://www.newgrounds.com/passport/mode/iframe",
				}

				pagetext = self.wg.getpage(action_target, postData=logondict, addlHeaders=extraHeaders)
				pagetext = self.wg.getpage(self.urlBase)

				if settings["ng"]["username"] in pagetext:

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

		dlBar = soup.find('div', class_='image-enlarged')

		if dlBar:
			img = dlBar.img
			if img and img.get("src", None):
				return img.get("src")

		direct_image = soup.find("img", itemprop="image")
		if direct_image:
			if direct_image and direct_image.get("src", None):
				return direct_image.get("src")


		raise ValueError("Wat?")

	def _extractTitleDescription(self, soup):
		title = soup.find('h2', itemprop='name')
		title = title.get_text().strip()

		desc = soup.find('div', id='author_comments')

		tags = soup.find('dd', class_='tags')

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


		date_meta = soup.find("meta", itemprop='datePublished')
		dstr = date_meta.get("content")
		dval = dateparser.parse(dstr).replace(tzinfo=None)


		return title, desc, dval

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):

		soup = self.wg.getSoup(artPageUrl)


		imageURL = self._getContentUrlFromPage(soup)

		# Cache busting? Anyways, trim it off, so we don't
		# fetch dupe images.
		imageURL = imageURL.split("?")[0]

		itemTitle, itemCaption, itemDate = self._extractTitleDescription(soup)

		if not imageURL:
			self.log.error("OH NOES!!! No image on page = %s", artPageUrl)
			raise ValueError("No image found!")

		urlPath = urllib.parse.urlparse(imageURL).path
		fName = urlPath.split("/")[-1]

		if not fName:
			self.log.error("OH NOES!!! No filename for image on page = %s", artPageUrl)
			raise ValueError("No filename found!")


		filePath = os.path.join(dlPathBase, fName)

		self.log.info("			Filename         = %s", fName)
		self.log.info("			Page Image Title = %s", itemTitle)
		self.log.info("			FileURL          = %s", imageURL)
		self.log.info("			dlPath           = %s", filePath)
		self.log.info("			timestamp        = %s", itemDate)

		if self._checkFileExists(filePath):
			self.log.info("Exists, skipping...")
			return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=itemTitle, postTime=itemDate)
		else:
			imgdat = self.wg.getpage(imageURL, addlHeaders={'referer':artPageUrl})


			# For text, the URL fetcher returns decoded strings, rather then bytes.
			# Therefore, if the file is a string type, we encode it with utf-8
			# so we can write it to a file.
			if isinstance(imgdat, str):
				imgdat = imgdat.encode(encoding='UTF-8')

			filePath = self.save_file(filePath, imgdat)
			if not filePath:
				return self.build_page_ret(status="Failed", fqDlPath=None)

			self.log.info("Successfully got: %s" % imageURL)
			return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=itemTitle, postTime=itemDate)

	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		basePage = "https://{user}.newgrounds.com/".format(user=artist)

		page = self.wg.getSoup(basePage)
		stats = page.find('div', class_='scroll-area')
		if not stats:
			return None

		for header_btn in stats.find_all('a', class_='user-header-button '):
			dtype = header_btn.find("span").get_text(strip=True)
			dval  = header_btn.find("strong").get_text(strip=True)

			if dtype == 'ART':
				ret = int(dval)
				self.log.info("Artist %s should have %s gallery items.", artist, ret)
				return ret

		return None



	def _getItemsOnPage(self, galBaseUrl, in_json):

		links = set()

		for year in in_json.get('years', {}).values():
			for item in year.get('items', []):
				soup = bs4.BeautifulSoup(item, "lxml")
				fqurl = urllib.parse.urljoin(galBaseUrl, soup.a['href'])
				links.add(fqurl)

		have_next = in_json.get('more', None)

		if have_next:
			have_next = urllib.parse.urljoin(galBaseUrl, have_next)


		return links, have_next


	def _getArtItems(self, artist):

		baseUrl = 'https://{user}.newgrounds.com/art'.format(user=artist)
		basesoup = self.wg.getSoup(baseUrl)


		pageurl = "https://{user}.newgrounds.com/art/page/{page}"

		nextUrl = pageurl.format(user=artist, page=1)
		ret = set()
		while nextUrl:

			if not flags.run:
				break

			self.log.info("Getting = '%s'", nextUrl)

			extraHeaders = {
						"referer"          : baseUrl,
						"x-requested-with" : 'XMLHttpRequest',
			}


			pg_json = self.wg.getJson(nextUrl, addlHeaders=extraHeaders)

			if pg_json is False:
				self.log.error("Cannot get Page")
				return set()

			new, nextUrl = self._getItemsOnPage(baseUrl, pg_json)
			new = new - ret
			self.log.info("Retrieved %s new items on page", len(new))
			ret |= new

		self.log.info("Found %s links" % (len(ret)))

		return ret


	def _getGalleries(self, artist):

		assert artist == artist.strip()

		artlinks = self._getArtItems(artist)

		return artlinks

