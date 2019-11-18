
import os
import os.path
import traceback
import re
import pprint
import time
import json
import datetime
import urllib.request
import urllib.parse
import random

import dateparser
import bs4
import pixivpy3

import flags
from settings import settings
import xascraper.modules.scraper_base
from xascraper.modules import exceptions

class GetPX(xascraper.modules.scraper_base.ScraperBase):

	pluginShortName = "px"
	pluginName     = "PxGet"

	urlBase         = "http://www.pixiv.net/"
	ovwMode         = "Check Files"

	numThreads      = 1

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.aapi = pixivpy3.AppPixivAPI()
		self.papi = pixivpy3.PixivAPI()

		saved_auth = self.get_param_cache()

		if saved_auth:
			self.log.info("Using cached auth")
			self.aapi.set_auth(access_token=saved_auth['a_access_token'], refresh_token=saved_auth['a_refresh_token'])
			self.papi.set_auth(access_token=saved_auth['p_access_token'], refresh_token=saved_auth['p_refresh_token'])


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def checkCookie(self):
		if not self.papi.access_token:
			return False, "Do not have Pixiv Cookies"

		try:
			following = self.papi.me_following()
			# {'errors': {'system': {'message': 'The access token provided is invalid.'}},
			#  'has_error': True,
			#  'status': 'failure'}

			if 'has_error' in following and following['has_error'] == True:
				tried = self.papi.auth()
				return False, "Auth failed!"


			return True, "Have Pixiv Auth Token:\n	-> %s" % (self.papi.access_token)

		except Exception as e:
			return False, "Do not have Pixiv Cookies"


	def getCookie(self):
		self.log.info("Pixiv Getting cookie")

		self.papi.login(username=settings[self.pluginShortName]["username"], password=settings[self.pluginShortName]["password"])
		# self.aapi.login(username=settings[self.pluginShortName]["username"], password=settings[self.pluginShortName]["password"])

		if self.papi.access_token and self.aapi.access_token:

			config = {
				'p_access_token'  : self.papi.access_token,
				'a_access_token'  : self.aapi.access_token,
				'p_refresh_token' : self.papi.refresh_token,
				'a_refresh_token' : self.aapi.refresh_token,
				}
			self.set_param_cache(config)

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


	def __papi_download(self, url, referer='https://app-api.pixiv.net/'):
		"""Download image to file (use 6.0 app-api)"""
		response = self.papi.requests_call('GET', url, headers={ 'Referer': referer }, stream=True)
		return response.raw.read()


	def _extractTitleDescription(self, meta):
		itemTitle   = meta['title']
		itemCaption = meta['caption']
		postTime    = dateparser.parse(meta['reuploaded_time'])
		postTags    = [tmp for tmp in meta['tags']]
		postTags.append("sanity level %s" % meta['sanity_level'])
		return itemTitle, itemCaption, postTime, postTags

	def _get_best_ugoira_from_set(self, imgset):
		if 'ugoira1920x1080' in imgset:
			return imgset['ugoira1920x1080']
		if 'ugoira600x600' in imgset:
			self.log.warning("No large image (found ugoira600x600)?")
			return imgset['ugoira600x600']
		raise RuntimeError("No ugoira1920x1080 or ugoira600x600 images!")

	def _get_best_image_from_set(self, imgset):
		if 'large' in imgset:
			if not 'img-original' in imgset['large']:
				self.log.warning("large image isn't marked original?")
			return imgset['large']
		if 'medium' in imgset:
			self.log.warning("No large image (found medium)?")
			return imgset['medium']
		if 'small' in imgset:
			self.log.warning("No large image (found small)?")
			return imgset['small']
		raise RuntimeError("No large, medium or small images!")

	def _getManga(self, dlPathBase, item_meta):
		itemTitle, itemCaption, postTime, postTags = self._extractTitleDescription(item_meta)

		regx4 = re.compile(r"http://.+/")				# FileName RE

		self.log.info("			postTime = %s", postTime)
		self.log.info("			postTags = %s", postTags)
		self.log.info("Saving image set")

		if 'metadata' not in item_meta:
			self.log.warning("Missing 'metadata' member!")
			if item['page_count'] == 1:
				self.log.warning("Treating as single-image item!")
				return self._getSinglePageContent(dlPathBase, item_mete)
			pprint.pprint(item_meta)
			raise exceptions.CannotFindContentException("Missing 'metadata' member!")

		if item_meta['metadata'] is None:
			self.log.error("Item metadata is None!")
			pprint.pprint(item_meta)
			raise exceptions.CannotFindContentException("'metadata' member is None!")

		if 'pages' not in item_meta['metadata']:
			self.log.error("Missing 'pages' member!")
			pprint.pprint(item_meta)
			raise exceptions.CannotFindContentException("Missing 'pages' member!")

		images = []
		index = 1
		for imagedat in item_meta['metadata']['pages']:
			imgurl = self._get_best_image_from_set(imagedat['image_urls'])
			fcont = self.__papi_download(imgurl)
			fname = regx4.sub("" , imgurl)
			fname = fname.rsplit("?")[0]
			fname = fname.rsplit("/")[-1]
			fname = "%04d - %s" % (index, fname)
			index += 1
			self.log.info("			Filename = %s", fname)
			self.log.info("			FileURL = %s", imgurl)
			file_path = os.path.join(dlPathBase, fname)
			saved_to = self.save_file(file_path, fcont)

			images.append(saved_to)

		return self.build_page_ret(status="Succeeded", fqDlPath=images, pageDesc=itemCaption, pageTitle=itemTitle, postTags=postTags, postTime=postTime)



	def _getSinglePageContent(self, dlPathBase, item_meta):
		itemTitle, itemCaption, postTime, postTags = self._extractTitleDescription(item_meta)
		imgurl   = self._get_best_image_from_set(item_meta['image_urls'])

		fcont = self.__papi_download(imgurl)

		regx4 = re.compile(r"http://.+/")				# FileName RE
		fname = regx4.sub("" , imgurl)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.
		fname = fname.rsplit("/")[-1]

		self.log.info("			Filename = %s", fname)
		self.log.info("			FileURL = %s", imgurl)
		self.log.info("			postTime = %s", postTime)
		self.log.info("			postTags = %s", postTags)

		file_path = os.path.join(dlPathBase, fname)
		saved_to = self.save_file(file_path, fcont)

		return self.build_page_ret(status="Succeeded", fqDlPath=[saved_to], pageDesc=itemCaption, pageTitle=itemTitle, postTags=postTags, postTime=postTime, content_structured={'metadata':item_meta['metadata']})


	def _getAnimation(self, dlPathBase, item_meta):
		itemTitle, itemCaption, postTime, postTags = self._extractTitleDescription(item_meta)
		imgurl   = self._get_best_ugoira_from_set(item_meta['metadata']['zip_urls'])

		pprint.pprint(item_meta)

		fcont = self.__papi_download(imgurl)

		regx4 = re.compile(r"http://.+/")				# FileName RE
		fname = regx4.sub("" , imgurl)
		fname = fname.rsplit("?")[0] 		# Sometimes there is some PHP stuff tacked on the end of the Image URL. Split on the indicator("?"), and throw away everything after it.
		fname = fname.rsplit("/")[-1]

		self.log.info("			Filename = %s", fname)
		self.log.info("			FileURL = %s", imgurl)
		self.log.info("			postTime = %s", postTime)
		self.log.info("			postTags = %s", postTags)

		file_path = os.path.join(dlPathBase, fname)
		saved_to = self.save_file(file_path, fcont)

		# TODO: Unpack ugoira unto a apng/gif (or at least a set of files)
		return self.build_page_ret(status="Succeeded", fqDlPath=[saved_to], pageDesc=itemCaption, pageTitle=itemTitle, postTags=postTags, postTime=postTime, content_structured={'metadata':item_meta['metadata']})


	def _getIllustration(self, artistName, dlPathBase, item_id):
		meta = self.papi.works(item_id)
		# pprint.pprint(meta)

		if not meta['status'] == 'success':
			return self.build_page_ret(status="Failed", fqDlPath=None)

		assert len(meta['response']) == 1

		resp = meta['response'][0]

		if resp is None:
			self.log.error("No metadata in response!")

		if resp['type'] == 'ugoira':
			ret = self._getAnimation(dlPathBase, resp)
			return ret

		if resp['type'] == 'manga':
			ret = self._getManga(dlPathBase, resp)
			return ret

		if resp['type'] == 'illustration':
			ret = self._getSinglePageContent(dlPathBase, resp)
			return ret

		raise RuntimeError("Content type not known: '%s'" % resp['type'])




	def _getArtPage(self, dlPathBase, item_params, artistName):
		'''
		Pixiv does a whole lot of referrer sniffing. They block images, and do page redirects if you don't submit the correct referrer.
		Also, I *think* they will block flooding, so that's the reason for the delays everywhere.
		'''

		params = json.loads(item_params)
		item_type = params['type']
		item_id   = params['id']

		try:

			# So my previous migration just categorized EVERYTHING as a illustration. Properly, the dispatch should be
			# done here for type, instead of in _getIllustration. However, doing it there doesn't cause additional work, it seems harmless.
			if item_type in ('illustration', 'manga', 'ugoira'):
				ret = self._getIllustration(artistName, dlPathBase, item_id)
				time.sleep(random.triangular(1,3,5))
				return ret

		except pixivpy3.PixivError as e:
			raise exceptions.RetryException("Error: '%s'" % e)

		raise RuntimeError("Unknown item type: '%s' for artist:item_id -> %s -> %s" % (item_type, artistName, item_id))

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getTotalArtCount(self, artist):
		aid = int(artist)
		items = self.papi.users_works(aid, include_stats=False)
		if items['status'] != 'success':
			self.log.error("Error while attempting to get artist gallery content for ID %s!!", artist)
			for line in traceback.format_exc().split("\n"):
				self.log.error(line)
			for line in pprint.pformat(items).split("\n"):
				self.log.error(line)


			raise exceptions.NotLoggedInException("Failed to get artist page?")


		return items['pagination']['total']


	def _getItemsOnPage(self, inSoup):

		links = set()

		imgItems = inSoup.find_all("li", class_="image-item")
		for tag in imgItems:
			url = urllib.parse.urljoin(self.urlBase, tag.a["href"])
			links.add(url)

		return links


	def _getGalleries(self, artist):
		aid = int(artist)

		artlinks = set()

		try:
			items = self.papi.users_works(aid, include_stats=False)
			artlinks.update(json.dumps({
					"id":   tmp["id"],
					"type": tmp["type"],
				}, sort_keys=True) for tmp in items['response'])

			while items['pagination']['next']:
				items = self.papi.users_works(aid, page=items['pagination']['next'], include_stats=False)
				artlinks.update(json.dumps({
						"id":   tmp["id"],
						"type": tmp["type"],
					}, sort_keys=True) for tmp in items['response'])
				self.log.info("Found %s links so far", len(artlinks))

				time.sleep(random.triangular(3,5,15))

			self.log.info("Found %s links", (len(artlinks)))
		except KeyError:
			self.log.error("Error while attempting to get gallery listing!")
			for line in traceback.format_exc().split("\n"):
				self.log.error(line)

			self.log.error("Aborting run!")

			raise exceptions.RetryException("What?")

		return artlinks


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):
		self.checkLogin()
		self.log.info("Getting list of favourite artists.")


		self.log.info("Fetching public follows")
		following = self.papi.me_following()
		resultList = set(str(tmp['id']) for tmp in following['response'])
		while following['pagination']['next']:
			following = self.papi.me_following(page=following['pagination']['next'])
			if not following['status'] == 'success':
				self.log.error("Failed on fetch!")
				pprint.pprint(following)
				raise RuntimeError("Wat?")

			resultList |= set(str(tmp['id']) for tmp in following['response'])
			self.log.info("Names found so far - %s", len(resultList))
			time.sleep(1)



		self.log.info("Fetching private follows")
		following = self.papi.me_following(publicity='private')
		resultList |= set(str(tmp['id']) for tmp in following['response'])
		while following['pagination']['next']:
			following = self.papi.me_following(page=following['pagination']['next'], publicity='private')
			if not following['status'] == 'success':
				self.log.error("Failed on fetch!")
				pprint.pprint(following)
				raise RuntimeError("Wat?")
			resultList |= set(str(tmp['id']) for tmp in following['response'])
			self.log.info("Names found so far - %s", len(resultList))
			time.sleep(1)

		self.log.info("Found %d Names", len(resultList))

		self.log.info("Inserting IDs into DB")
		# Push the pixiv name list into the DB
		with self.db.context_sess() as sess:
			for name in resultList:
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()
				if not res:
					self.log.info("Need to insert name: %s", name)
					sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name))
					sess.commit()


		return super().getNameList()



if __name__ == '__main__':

	import logSetup
	logSetup.initLogging()

	ins = GetPX()
	print("Checking auth")
	ins.checkLogin()
	# ins.checkCookie()
	# ins.getCookie()
	# ins.getNameList()
	# print(ins)
	# print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	print("Getting Galleries")

	# count = ins._getTotalArtCount("512775")
	# print(count)
	# ret = ins._getArtPage("xxx", '{"type" : "illustration", "id" : 76882251}', "xxx")
	# print(ret)



