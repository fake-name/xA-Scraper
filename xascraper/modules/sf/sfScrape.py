
import os
import os.path
import traceback
import re
import json
import datetime
import urllib.request
import urllib.parse
import dateparser
import bs4
import WebRequest
from settings import settings
import flags

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

def makeFilenameSafe(inStr):

	# FUCK YOU SMART-QUOTES.
	inStr = inStr.replace("“",  " ") \
				 .replace("”",  " ")

	inStr = inStr.replace("%20", " ") \
				 .replace("<",  " ") \
				 .replace(">",  " ") \
				 .replace(":",  " ") \
				 .replace("\"", " ") \
				 .replace("/",  " ") \
				 .replace("\\", " ") \
				 .replace("|",  " ") \
				 .replace("?",  " ") \
				 .replace("*",  " ") \
				 .replace('"', " ")

	# zero-width space bullshit (goddammit unicode)
	inStr = inStr.replace("\u2009",  " ") \
				 .replace("\u200A",  " ") \
				 .replace("\u200B",  " ") \
				 .replace("\u200C",  " ") \
				 .replace("\u200D",  " ") \
				 .replace("\uFEFF",  " ")

	# Collapse all the repeated spaces down.
	while inStr.find("  ")+1:
		inStr = inStr.replace("  ", " ")


	# inStr = inStr.rstrip(".")  # Windows file names can't end in dot. For some reason.
	# Fukkit, disabling. Just run on linux.

	inStr = inStr.rstrip("! ")   # Clean up trailing exclamation points
	inStr = inStr.strip(" ")    # And can't have leading or trailing spaces

	return inStr


class GetSF(xascraper.modules.scraper_base.ScraperBase):

	settingsDictKey = "sf"

	pluginName = "SfGet"

	urlBase = "https://www.sofurry.com/"

	ovwMode = "Check Files"

	numThreads = 1

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):


		pagetext = self.wg.getpage('https://www.sofurry.com/user/preferences')
		if '<a href="https://%s.sofurry.com/" class="avatar">' % settings["sf"]["username"] in pagetext:
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

			logondict = {
							"yt0"                        : "Login",
							"LoginForm[sfLoginUsername]" : settings["sf"]["username"],
							"LoginForm[sfLoginPassword]" : settings["sf"]["password"],
							"YII_CSRF_TOKEN"             : ""
						}

			extraHeaders = {
						"Referer"       : "https://www.sofurry.com/user/login",
			}

			pagetext = self.wg.getpage('https://www.sofurry.com/user/login', postData=logondict, addlHeaders=extraHeaders)
			if '<a href="https://%s.sofurry.com/" class="avatar">' % settings["sf"]["username"] in pagetext:
				print("Login Succeeded")
				self.wg.saveCookies()
				return True, "Logged In"
			else:
				self.log.error("Login failed!")
				return False, "Failed to log in"

		except Exception:
			self.log.critical("Caught Error")
			self.log.critical(traceback.format_exc())
			traceback.print_exc()
			return "Login Failed"




	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getContentUrlFromPage(self, soup):

		dl_link = soup.find('a', id='sfDownload')

		if dl_link:
			itemUrl = urllib.parse.urljoin(self.urlBase, dl_link['href'])
			return itemUrl

		inline_img_div = soup.find('div', id='sfContentImage')
		if inline_img_div and inline_img_div.img:
			itemUrl = urllib.parse.urljoin(self.urlBase, inline_img_div.img['src'])
			return itemUrl

		return None

	def _extractTitleDescription(self, soup):
		title = soup.find('span', id='sfContentTitle')
		title = title.get_text().strip()

		desc_foreward = soup.find('div', id='sfContentDescription')
		desc_div = soup.find('div', id='sfContentBody')

		for bad_input in desc_div.find_all("input", type='hidden'):
			bad_input.decompose()
		for bad_input in desc_div.find_all("input", type='submit'):
			bad_input.decompose()

		for bad_input in desc_div.find_all("div", style="display:none"):
			bad_input.unwrap()
		for bad_input in desc_div.find_all("form"):
			bad_input.unwrap()

		for empty_tag in desc_div.find_all("a"):
			if empty_tag.get_text().strip() == "":
				empty_tag.decompose()

		tags = soup.find('div', id='submission_tags')

		# Horrible hack using ** to work around the fact that 'class' is a reserved keyword
		tagDiv = soup.new_tag('div', class_='tags')

		tagHeader = soup.new_tag('b')
		tagHeader.append('Tags:')
		tagDiv.append(tagHeader)

		plain_tags = []
		for tag_section in tags.find_all("div", class_='section'):
			type = tag_section.find("div", class_='section-title')
			typename = type.get_text().strip().split(" ")[0]
			for tag in tag_section.find_all('a', class_='sf-tag'):
				plain_tags.append(tag.get_text().strip())
				new = soup.new_tag('div', **{'class' : 'tag ' + typename.lower()})
				new.append(tag.get_text())
				tagDiv.append(new)

		desc_div.append(tagDiv)
		desc = str(desc_foreward.prettify()) + "\n<br />\n" + str(desc_div.prettify())

		timestamp = datetime.datetime.min
		stats_sections = soup.find_all("div", class_='section-content')
		for section in stats_sections:
			context = section.get_text()
			if "Posted" in context:
				context = context.split("\n")
				for line in context:
					if "Posted" in line:
						print("Timestamp line:", line)
						timestamp = dateparser.parse(line[7:])
						print("Parsed:", timestamp)

		return title, desc, plain_tags, timestamp

	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		artPageUrl = artPageUrl.lower()
		params = json.loads(artPageUrl)
		soup = self.wg.getSoup(params['url'])
		soups = str(soup)
		if 'This submission has been deleted.' in soups:
			self.log.warning("Item %s has been deleted by the poster!", artPageUrl)
			return self.build_page_ret(status="Deleted", fqDlPath=None)

		imageURL = self._getContentUrlFromPage(soup)
		itemTitle, itemCaption, itemTags, postTime = self._extractTitleDescription(soup)


		if not imageURL:
			if not ("/stories" in artPageUrl or "/journals" in artPageUrl):
				self.log.error("Warning! No image on page = %s", artPageUrl)
			return self.build_page_ret(status="Exists", fqDlPath=[], pageDesc=itemCaption, pageTitle=itemTitle, postTags=itemTags, postTime=postTime)
		else:
			fName = makeFilenameSafe(itemTitle)

			if not fName:
				self.log.error("OH NOES!!! No filename for image on page = " + artPageUrl)
				raise ValueError("No filename found!")


			filePath = os.path.join(dlPathBase, fName)

			self.log.info("	Filename         = %s", fName)

			self.log.info("	Page Image Title = %s", itemTitle)
			self.log.info("	FileURL          = %s", imageURL)
			self.log.info("	dlPath           = %s", filePath)

			if self._checkFileExists(filePath):
				self.log.info("Exists, skipping...")
				return self.build_page_ret(status="Exists", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=itemTitle, postTags=itemTags, postTime=postTime)
			else:
				imgdat, imName = self.wg.getFileAndName(imageURL, addlHeaders={'Referer':artPageUrl})

				if (imName.startswith("'") and imName.endswith("'")) or \
					(imName.startswith('"') and imName.endswith('"')):
					imName = imName[1:-1]



				# For text, the URL fetcher returns decoded strings, rather then bytes.
				# Therefore, if the file is a string type, we encode it with utf-8
				# so we can write it to a file.
				if isinstance(imgdat, str):
					imgdat = imgdat.encode(encoding='UTF-8')

				filePath = self.save_file(filePath, imgdat)
				if not filePath:
					return self.build_page_ret(status="Failed", fqDlPath=None)

				return self.build_page_ret(status="Succeeded", fqDlPath=[filePath], pageDesc=itemCaption, pageTitle=itemTitle, postTags=itemTags, postTime=postTime)

		return self.build_page_ret(status="Failed", fqDlPath=None)


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		try:
			soup = self.wg.getSoup("https://%s.sofurry.com/" % artist.strip().lower())
		except WebRequest.FetchFailureError as e:
			if e.err_code == 404:
				raise exceptions.AccountDisabledException("Account seems to have been removed!")
			raise e

		# This is probably stupidly brittle
		subdiv = soup.find("span", class_='sfTextMedLight', text=re.compile('submissions', flags=re.IGNORECASE))
		tgt = subdiv.parent.span.get_text()

		# Dump number separators
		tgt = tgt.replace(",", "")

		return (int(tgt))




	def _dumpUrl(self, url, art_type, directory="/"):
		data = {
			'url'       : url,
			'directory' : directory,
			'type'      : art_type,
		}
		return json.dumps(data, sort_keys=True)

	def _getFolders(self, soup, path, baseUrl):
		folder_div = soup.find('div', class_='sfBrowseListFolders')
		if not folder_div:
			return set()
		folder_div = folder_div.find('div', class_='items')
		folders = folder_div.find_all('div', recursive=False)

		ret = set()
		for folder in folders:
			url = folder.a['href']
			# Fix protocol relative URL (if present)
			url = urllib.parse.urljoin(baseUrl, url)

			ret |= self._getContent(path + "/" + folder.get_text().strip(), url)

		return ret

	def _getItems(self, soup, path, baseUrl):
		item_div = soup.find('div', class_='sfBrowseListContent')

		ret  = set()
		pager = item_div.find('div', class_='pager')
		if pager:
			nextpg = pager.find('li', class_='next')
			if not "hidden" in nextpg['class']:
				url = nextpg.a['href']
				# Fix protocol relative URL (if present)
				url = urllib.parse.urljoin(baseUrl, url)
				ret |= self._getContent(path=path, url=url)

		for artcontainer in item_div.find_all('div', class_='sfArtworkSmallWrapper'):
			link = artcontainer.find('a', class_='sfArtworkSmallInner')
			arturl = urllib.parse.urljoin(baseUrl, link['href'])
			link = self._dumpUrl(arturl, "artwork", path)
			ret.add(link)

		item_type = "journals" if baseUrl.startswith('/journals') else 'stories'

		for text_container in item_div.find_all('div', class_=re.compile(r'sf-story(?:-big)?-headline', re.IGNORECASE)):
			journalurl = urllib.parse.urljoin(baseUrl, text_container.a['href'])
			link = self._dumpUrl(journalurl, item_type, path)
			ret.add(link)


		return ret


	def _getContent(self, path, url):
		soup = self.wg.getSoup(url)
		ret  = set()

		# Since folders are common across all sequence pages, only enter them if we're on the first page
		if not ("art-page=" in url or "journals-page=" in url or "stories-page=" in url):
			ret |= self._getFolders(soup, path, url)
		ret |= self._getItems(soup, path, url)

		return ret

	def _getGalleries(self, artist):

		artist = artist.strip().lower()

		baseUrl = 'https://{user}.sofurry.com/'.format(user=artist)

		items  = set()

		items |= self._getContent(path='/stories',  url="{base}stories".format(base=baseUrl))
		items |= self._getContent(path='/artwork',  url="{base}artwork".format(base=baseUrl))
		items |= self._getContent(path='/journals', url="{base}journals".format(base=baseUrl))


		self.log.info("Found %s links", len(items))
		return items






if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	ins = GetSF()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	ins._getArtPage("xxxx", '{"url":"https://www.sofurry.com/view/857034"}', 'testtt')





