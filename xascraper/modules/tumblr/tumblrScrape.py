
import os
import os.path
import traceback
import urllib.parse
import concurrent.futures
import datetime
import signal
import random
from settings import settings
from tumblpy import Tumblpy

import flags
import xascraper.modules.scraper_base


class FetchError(Exception):
	pass
class MissingContentError(Exception):
	pass

class GetTR(xascraper.modules.scraper_base.ScraperBase):

	settingsDictKey = "tum"

	pluginName = "TumblrGet"

	urlBase = "http://{user}.tumblr.com/"

	ovwMode = "Check Files"

	numThreads = 2



	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.t = self.getToken()


	def checkCookie(self):
		# I dunno if this is the "proper" way to check auth, but wth.
		tum_url = self.t.post('user/info')['user']['blogs'][0]['url']
		tum_uname = settings['tum']['username']
		have_auth = tum_uname.lower() in tum_url.lower()
		self.log.info("Can access account: %s", have_auth)
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
		pass



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

		have = self._checkHaveUrl(artistName, post_struct['post_url'])
		if have:
			self.log.info("Have content for url! %s, %s", have, post_struct['post_url'])
			return

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

		self._updatePreviouslyRetreived(artist=orga, release_meta=pgurl, state='complete')


	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------




	def _getGalleries(self, artist):

		artist = artist.strip()

		baseUrl = self.urlBase.format(user=artist)

		post_count = 0
		offset = 0
		step   = 20
		while 1:
			self.log.info("Fetching posts at offset: %s for user %s", offset, artist)
			addposts = self.t.get('posts', blog_url=baseUrl, params={"limit" : step, 'offset':offset})
			offset += step
			if len(addposts['posts']) == 0:
				break

			for post in addposts['posts']:
				yield post

			post_count += 1

		self.log.info("Found %s links", post_count)


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

		# artPages = self._getGalleries(artist)

		# oldArt = self._getPreviouslyRetreived(artist)


		# while len(artPages) > 0:
		for post_struct in self._getGalleries(artist):
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

			# self.log.info("Pages for %s remaining = %s", artist, len(artPages))
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
				self.log.critical("Tumblr Authentication is failing! Are your API keys correct? Cannot continue!")
				return False


			errored = False

			random.shuffle(nameList)

			# Farm out requests to the thread-pool
			with concurrent.futures.ProcessPoolExecutor(max_workers=self.numThreads) as executor:

				future_to_url = {}
				for aId, aName in nameList:
					future_to_url[executor.submit(GetTR.get_artist_proc, aName, ctrlNamespace)] = aName

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


def mgr_init():
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	print('initialized manager')

def signal_handler(dummy_signal, dummy_frame):
	if flags.namespace.run:
		flags.namespace.run = False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

def run_local():
	import multiprocessing

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	signal.signal(signal.SIGINT, signal_handler)

	print(sys.argv)
	ins = GetTR()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	# ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	ins.go(ctrlNamespace=flags.namespace)


if __name__ == '__main__':

	import sys
	import logSetup
	logSetup.initLogging()

	run_local()

