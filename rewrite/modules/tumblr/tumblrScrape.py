
import os
import os.path
import traceback
import urllib.parse
import concurrent.futures
import datetime
from settings import settings
from tumblpy import Tumblpy

import rewrite.modules.scraper_base


class FetchError(Exception):
	pass
class MissingContentError(Exception):
	pass

class GetTumblr(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "tum"

	pluginName = "TumblrGet"

	urlBase = "http://{user}.tumblr.com/"

	ovwMode = "Check Files"

	numThreads = 5



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
		desc  = post_struct['caption'] if 'caption' in post_struct else ""
		raw_tags  = post_struct['tags'] if 'tags' in post_struct else []
		html_tags = "".join(["<div><ul class='tags'>"] +
			["<li>{tag}</li>".format(tag=tag) for tag in raw_tags] +
			["</ul></div>"])

		self._updatePreviouslyRetreived(artist=orga, release_meta=pgurl, pageDesc=desc+html_tags, pageTitle=title, postTags=raw_tags)

		if "photos" in post_struct:
			contenturls = [tmp['original_size']['url'] for tmp in post_struct['photos']]
		else:
			raise MissingContentError("Cannot find content!")

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
			if len(fName) == 0:
				raise FetchError("Missing Filename for file '%s' (url: %s)" % (fName, url))

			filePath = os.path.join(dlPathBase, fName)

			# NFI how this was happening.
			if filePath.startswith("{"):
				filePath = filePath[1:]

			if isinstance(content, str):
				content = content.encode(encoding='UTF-8')


			self.log.info("Saving file %s to path %s", fName, filePath)
			with open(filePath, "wb") as fp:								# Open file for saving image (Binary)
				fp.write(content)						# Write Image to File

			self._updatePreviouslyRetreived(artist=orga, release_meta=pgurl, fqDlPath=filePath, seqNum=seq)
			seq += 1


	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------




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
			except urllib.error.URLError:  # WebGetRobust throws urlerrors
				self.log.error("Page Retrieval failed!")
				self.log.error("Post Struct = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				# self._updateUnableToRetrieve(artist, pageURL)
			except MissingContentError:
				self.log.error("Page Retrieval failed!")
				self.log.error("Continuing on next page")
			except FetchError:
				self.log.error("Page Retrieval failed!")
				self.log.error("Post Struct = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				self.log.error("Continuing on next page")
				# self._updateUnableToRetrieve(artist, pageURL)
			except:
				self.log.error("Unknown error in page retrieval!")
				self.log.error("Post Struct = '%s'", post_struct)
				self.log.error(traceback.format_exc())
				# self._updateUnableToRetrieve(artist, pageURL)

			self.log.info("Pages for %s remaining = %s", artist, len(artPages))
			if ctrlNamespace.run == False:
				break

		# self._updatePreviouslyRetreived(artist, tmp)

		self.log.info("Successfully retreived content for artist %s", artist)
		return False


	@classmethod
	def get_artist_proc(cls, aName, ctrlNamespace):
		try:
			clsinstance = cls()
			return clsinstance.getArtist(artist=aName, ctrlNamespace=ctrlNamespace)
		except Exception:
			traceback.print_exc()
			return True

	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")
		is_another_active = self.getRunningStatus(self.settingsDictKey)

		if is_another_active:
			self.log.error("Another instance of the %s scraper is running.", self.targetShortName)
			self.log.error("Not starting")
			return
		try:
			self.updateRunningStatus(self.settingsDictKey, True)
			startTime = datetime.datetime.now()
			self.updateLastRunStartTime(self.settingsDictKey, startTime)

			if not nameList:
				nameList = self.getNameList()

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.info("Do not have login cookie. Retreiving one now.")
				cookieStatus = self.getCookie()
				self.log.info("Login attempt status = %s.", cookieStatus)

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.critical("Failed to download cookie! Exiting!")
				return False


			errored = False

			# Farm out requests to the thread-pool
			with concurrent.futures.ProcessPoolExecutor(max_workers=self.numThreads) as executor:

				future_to_url = {}
				for aId, aName in nameList:
					future_to_url[executor.submit(GetTumblr.get_artist_proc, aName, ctrlNamespace)] = aName

				for future in concurrent.futures.as_completed(future_to_url):
					# aName = future_to_url[future]
					# res = future.result()
					errored  |= future.result()
					# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

			if errored:
				self.log.warn("Had errors!")

			runTime = datetime.datetime.now()-startTime
			self.updateLastRunDuration(self.settingsDictKey, runTime)

		finally:
			self.updateRunningStatus(self.settingsDictKey, False)

