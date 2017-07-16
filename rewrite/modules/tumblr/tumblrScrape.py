
import os
import os.path
import traceback
import re
import bs4
import psycopg2
import pprint
import urllib.request
import urllib.parse
from settings import settings
from tumblpy import Tumblpy

import rewrite.modules.scraper_base


class FetchError(Exception):
	pass

class GetTumblr(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "tum"

	pluginName = "TumblrGet"

	urlBase = "http://{user}.tumblr.com/"

	ovwMode = "Check Files"

	numThreads = 1



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.t = self.getToken()


	def checkCookie(self):
		# I dunno if this is the "proper" way to check auth, but wth.
		have_auth = settings['tum']['username'] in self.t.post('user/info')['user']['blogs'][0]['url']
		self.log.info("Have authentication: %s", have_auth)
		return have_auth, "Ok"


	def getToken(self):
		t = Tumblpy(
			settings['tum']['consumer_key'],
			settings['tum']['consumer_secret'],
			settings['tum']['token'],
			settings['tum']['token_secret'],
			)
		return t

	def getCookie(self):
		try:

			accessToken = self.getToken()

			#print soup.find_all("input")
			#print soup
			if accessToken:
				return True, "Logged In"

		except:
			self.log.critical("Caught Error")
			self.log.critical(traceback.format_exc())
			traceback.print_exc()
		return False, "Login Failed"




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


	def _getArtPage(self, post_struct, artistName):



		orga  = post_struct['blog_name']
		pgurl = post_struct['post_url']
		title = post_struct['summary']
		desc  = post_struct['caption']
		raw_tags  = post_struct['tags']
		tags = "".join(["<div><ul class='tags'>"] +
			["<li>{tag}</li>".format(tag=tag) for tag in raw_tags] +
			["</ul></div>"])

		self._updatePreviouslyRetreived(artist=orga, pageUrl=pgurl, fqDlPath=None, pageDesc=desc+tags, pageTitle=title, seqNum=seq, postTags=raw_tags)

		if "photos" in post_struct:
			contenturls = [tmp['original_size']['url'] for tmp in post_struct['photos']]
		else:
			raise FetchError("Cannot find content!")

		have = self._checkHaveUrl(artistName, pgurl)
		if have:
			self.log.info("Have content for url! %s, %s", have, pgurl)
			return

		dlPathBase = self.getDownloadPath(self.dlBasePath, orga)


		if not contenturls:
			self.log.error("OH NOES!!! No image on page = " + post_struct)
			raise FetchError("No content found!")

		seq = 1
		for url in contenturls:
			content, fName = self.wg.getFileAndName(url, addlHeaders={'Referer' : pgurl})
			filePath = os.path.join(dlPathBase, fName)

			if isinstance(content, str):
				content = content.encode(encoding='UTF-8')

			with open(filePath, "wb") as fp:								# Open file for saving image (Binary)
				fp.write(content)						# Write Image to File

			self._updatePreviouslyRetreived(artist=orga, pageUrl=pgurl, fqDlPath=filePath, pageDesc=desc+tags, pageTitle=title, seqNum=seq, postTags=raw_tags)
			seq += 1


	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def _getItemsOnPage(self, inSoup):

		links = set()
		itemUl = inSoup.find("ul", class_='thumbnail-grid')
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

	def _getPosts(self, baseUrl):

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





	def _getGalleries(self, artist):

		artlinks = set()
		artist = artist.strip()

		baseUrl = self.urlBase.format(user=artist)

		posts = []
		offset = 0
		step   = 20
		while 1:
			self.log.info("Fetching posts at offset: %s for user %s", offset, artist)
			addposts = self.t.get('posts', blog_url=baseUrl, params={"limit" : step, 'offset':offset})
			offset += step
			if len(addposts['posts']) == 0:
				break
			posts.extend(addposts['posts'])

		self.log.info("Found %s links" % (len(posts)))
		return posts

	def _getTotalArtCount(self):
		pass



	def getArtist(self, artist, ctrlNamespace):
		if ctrlNamespace.run == False:
			self.log.warning("Exiting early from %s due to run flag being unset", artist)
			return True

		artist = artist.lower()

		# return True

		self.log.info("GetArtist - %s", artist)
		self.setupDir(artist)

		artPages = self._getGalleries(artist)

		oldArt = self._getPreviouslyRetreived(artist)


		while len(artPages) > 0:
			post_struct = artPages.pop(0)
			pageURL = post_struct['post_url']

			try:
				self._getArtPage(post_struct, artist)
				# return

			except psycopg2.IntegrityError as e:
				import sys
				sys.exit()
			except urllib.error.URLError:  # WebGetRobust throws urlerrors
				self.log.error("Page Retrieval failed!")
				self.log.error("Source URL = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				# self._updateUnableToRetrieve(artist, pageURL)
			except FetchError:
				self.log.error("Page Retrieval failed!")
				self.log.error("Source URL = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				# self._updateUnableToRetrieve(artist, pageURL)
			except:
				self.log.error("Unknown error in page retrieval!")
				self.log.error("Source URL = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				# self._updateUnableToRetrieve(artist, pageURL)

			self.log.info("Pages for %s remaining = %s", artist, len(artPages))
			if ctrlNamespace.run == False:
				break






		# self._updatePreviouslyRetreived(artist, tmp)

		self.log.info("Successfully retreived content for artist %s", artist)
		return False
