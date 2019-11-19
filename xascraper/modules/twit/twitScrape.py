
import os
import os.path
import traceback
import urllib.parse
import concurrent.futures
import datetime
import random

from settings import settings
import xascraper.modules.scraper_base
from xascraper.modules import exceptions

from . import vendored_twitter_scrape

class GetTwit(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "twit"
	pluginName = "TwitGet"
	urlBase = "https://twitter.com/"
	ovwMode = "Check Files"
	numThreads = 1

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		return True, "No login required"

		# pagetext = self.wg.getpage(self.urlBase)
		# if settings["twit"]["username"] in pagetext:
		# 	return True, "Have as Cookie."
		# else:
		# 	return False, "Do not have as login Cookies"


	def getToken(self):
		self.log.info("Getting Entrance Cookie")
		soup = self.wg.getSoup('https://twitter.com/login')
		inputs = soup.find_all("input")

		for intag in inputs:
			if 'name' in intag.attrs and intag['name'] == 'authenticity_token':
				return intag['value']

		raise RuntimeError("No access toke found!")


	def getCookie(self):
		try:
			accessToken = self.getToken()

			logondict = {"authenticity_token"           : accessToken,
						"session[username_or_email]"    : settings["twit"]["username"],
						"session[password]"             : settings["twit"]["password"]
						}

			extraHeaders = {
						"Referer"       : "https://twitter.com/login",
			}

			pagetext = self.wg.getpage('https://twitter.com/sessions', postData=logondict, addlHeaders=extraHeaders)
			with open('temp.html', 'w', encoding="utf-8") as fp:
				fp.write(pagetext)
			if "\"isLoggedIn\":true" in pagetext:
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
	# Stubs to handle base class
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getGalleries(self, artist):
		pass

	def _getTotalArtCount(self):
		pass

	def _getContentUrlFromPage(self, soup):
		pass

	def _getArtPage(self, post_struct, artistName):
		pass

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Timeline Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _check_insert_tweet(self, src_user, aid, tweet):
		tw_user = tweet['tweet_author']
		tw_id     = tweet['tweetId']

		with self.db.context_sess() as sess:
			is_new = self._upsert_if_new(sess, aid, tw_id)

		if is_new:
			self.log.info("Have content for TweetID! %s, %s", tw_id, src_user)
			# return

		tweet_entries = tweet['entries']

		if tweet['isRetweet']:
			tw_title = "Retweet from %s by %s" % (tw_user, src_user)
		else:
			tw_title = "Tweet from %s" % (tw_user, )

		self._updatePreviouslyRetreived(
			artist             = src_user,
			release_meta       = tw_id,
			pageTitle          = tw_title,
			pageDesc           = tweet['text'],
			postTags           = tweet_entries['hashtags'],
			content_structured = tweet,
			)

		if tweet_entries['photos'] or tweet_entries['videos'] or tweet_entries['urls']:
			self.setupDir(tw_user)
		else:
			# Text-only tweet
			self._updatePreviouslyRetreived(artist=src_user, release_meta=tw_id, state='complete')
			return

		photos = tweet_entries['photos']
		videos = tweet_entries['videos']
		urls   = tweet_entries['urls']

		if urls and not (photos or videos):
			self.log.warning("Urls entry on tweet (%s). Don't know how to handle this yet!", tweet_entries)
			self._updatePreviouslyRetreived(artist=src_user, release_meta=tw_id, state='complete')
			return
		if videos and not (photos or urls):
			self.log.warning("Videos entry on tweet (%s). Don't know how to handle this yet!", tweet_entries)
			self._updatePreviouslyRetreived(artist=src_user, release_meta=tw_id, state='complete')
			return

		dlPathBase = self.getDownloadPath(self.dlBasePath, tw_user)

		postd = datetime.datetime.fromtimestamp(tweet['time'])
		tw_y = postd.strftime('%y')
		tw_m = int(postd.strftime('%m'))
		tw_d = int(postd.strftime('%d'))
		tw_ho = int(postd.strftime('%H'))
		tw_mi = int(postd.strftime('%M'))
		tw_se = int(postd.strftime('%S'))
		tw_p = postd.strftime('%p')
		tw_h = int(postd.strftime('%I'))

		seq = 1
		for url in photos:
			content, fName = self.wg.getFileAndName(url+":orig")
			# if len(fName) == 0:
			# 	raise FetchError("Missing Filename for file '%s' (url: %s)" % (fName, url))

			fExt = (fName.rpartition(':')[0]).rpartition('.')[2]
			fName = (fName.rpartition(':')[0]).rpartition('.')[0]

			try:
				fName = str(eval(settings['twit']['filePattern']))
			except KeyError:
				fName = "%s - %s - 20%s-%02i-%02i - %02i - %s" % (tw_user, tw_id, tw_y, tw_m, tw_d, seq, fName)

			filePath = os.path.join(dlPathBase, (fName+'.'+fExt))

			if isinstance(content, str):
				content = content.encode(encoding='UTF-8')

			self.log.info("Saving file %s to path %s", fName, filePath)
			with open(filePath, "wb") as fp:
				fp.write(content)

			self._updatePreviouslyRetreived(artist=src_user, release_meta=tw_id, fqDlPath=filePath, seqNum=seq)
			seq += 1

		self._updatePreviouslyRetreived(artist=src_user, release_meta=tw_id, state='complete')





	def getArtist(self, aid, artist, ctrlNamespace):
		if ctrlNamespace.run == False:
			self.log.warning("Exiting early from %s due to run flag being unset", artist)
			return True


		self.log.info("GetArtist - %s (ID: %s)", artist, aid)

		intf = vendored_twitter_scrape.TwitterFetcher()

		# while len(artPages) > 0:
		for tweet in intf.get_tweets(artist):

			self._check_insert_tweet(artist, aid, tweet)

			# self.log.info("Pages for %s remaining = %s", artist, len(artPages))
			if ctrlNamespace.run == False:
				break

		# self._updatePreviouslyRetreived(artist, tmp)

		self.log.info("Successfully retreived content for artist %s", artist)
		return False


	def go(self, nameList=None, ctrlNamespace=None):
		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")
		is_another_active = self.getRunningStatus(self.pluginShortName)

		if is_another_active:
			self.log.error("Another instance of the %s scraper is running.", self.pluginShortName)
			self.log.error("Not starting")
			return
		try:
			self.updateRunningStatus(self.pluginShortName, True)
			startTime = datetime.datetime.now()
			self.updateLastRunStartTime(self.pluginShortName, startTime)

			if not nameList:
				nameList = self.getNameList()

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.critical("Tumblr Authentication is failing! Are your API keys correct? Cannot continue!")
				return False

			errored = False

			random.shuffle(nameList)

			for aid, name in nameList:
				try:
					errored |= self.getArtist(aid=aid, artist=name, ctrlNamespace=ctrlNamespace)
				except Exception:
					for line in traceback.format_exc().split("\n"):
						self.log.error(line)
					errored |= True

			if errored:
				self.log.warning("Had errors!")

			runTime = datetime.datetime.now()-startTime
			self.updateLastRunDuration(self.pluginShortName, runTime)

		finally:
			self.updateRunningStatus(self.pluginShortName, False)

