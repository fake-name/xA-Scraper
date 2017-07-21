
import os
import os.path
import traceback
import datetime
import pytz
import dateutil.parser
import urllib.parse
import json
import pprint
from settings import settings

import rewrite.modules.scraper_base

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

class GetPatreon(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "pat"

	pluginName = "PatreonGet"

	urlBase = None

	ovwMode = "Check Files"

	numThreads = 1


	# Stubbed functions
	_getGalleries = None
	_getTotalArtCount = None


	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Cookie Management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


	def checkCookie(self):
		print("Checking login!")
		try:
			current = self.get_json("/current_user", retries=1)
		except Exception:
			print("Not logged in!")
			current = False

		if not current or current['data']['id'] == 0:
			return False, "Not logged in"
		else:
			return True, "Autheticated OK"


	def getCookie(self):
		if self.checkCookie()[0]:
			return True, "Already logged in"

		self.log.info("Not logged in. Doing login.")
		login_data = {
			"email"    : settings[self.settingsDictKey]['username'],
			"password" : settings[self.settingsDictKey]['password'],
		}

		current = self.get_json("/login", postData=login_data)

		self.log.info("Login results: %s", current)
		self.wg.syncCookiesFromFile()

		return self.checkCookie()

	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Internal utilities stuff
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_json(self, endpoint, postData = None, apikey = False, retries=3):
		if postData:
			postData = {"data" : postData}
			postData = json.dumps(postData)

		if apikey:
			apikey = "?api_key=1745177328c8a1d48100a9b14a1d38c1"
		else:
			apikey = ""

		print("")
		content = self.wg.getpage("https://api.patreon.com{endpoint}{api}".format(endpoint=endpoint, api=apikey),
			addlHeaders={
				"Accept"          : "application/json, text/plain, */*",
				"Referer"         : "https://www.patreon.com/login",
				"Origin"          : "https://www.patreon.com",
				"Host"            : "api.patreon.com",
				"Content-Type"    : "application/json; charset=UTF-8",
				"Accept-Encoding" : "gzip, deflate",
				"Pragma"          : "no-cache",
				"Cache-Control"   : "no-cache",
				},
			postData = postData,
			retryQuantity = retries)

		if content is None:
			self.log.error("Couldn't login! Please check username and password!")
			raise LoginFailure("Failed to login. Please check your username and password are correct!")

		content = content.decode("utf-8")
		vals = json.loads(content)
		return vals


	def current_user_info(self):
		current = self.get_json("/current_user?include=pledges&include=follows")
		return current


	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# # Individual page scraping
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_save_dir(self, aname):

		dirp = self.getDownloadPath(self.dlBasePath, aname)
		if not os.path.exists(dirp):
			os.makedirs(dirp)
		return dirp

	def save_file(self, aname, filename, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, filename)
		with open(fqpath, "wb") as fp:
			fp.write(filecontent)

	def save_json(self, aname, itemid, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, "pyson-posts")
		if not os.path.exists(fqpath):
			os.makedirs(fqpath)
		fqpath = os.path.join(fqpath, 'itemid-{id}.pyson'.format(id=itemid))
		with open(fqpath, "wb") as fp:
			fstr = pprint.pformat(filecontent)
			fp.write(fstr.encode("utf-8"))

	def save_image(self, aname, pid, fname, furl):
		print("Saving image: '%s'" % furl)
		fname = "{pid}-{fname}".format(pid=pid, fname=fname)
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, fname)
		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			content = self.wg.getpage(furl, addlHeaders={"Referer" : "https://www.patreon.com/home"})
			if content:
				self.save_file(aname, fname, content)
			else:
				self.log.error("Could not retreive content: ")
				self.log.error("%s", furl)
				return None
		return fqpath

	def save_attachment(self, aname, pid, dat_struct):
		print("Saving attachment: '%s'" % dat_struct['attributes']['url'])
		if dat_struct['attributes']['url'].startswith("https"):
			url = dat_struct['attributes']['url']
		else:
			url = "https:{url}".format(url=dat_struct['attributes']['url'])

		fname = "{pid}-{aid}-{fname}".format(pid=pid, aid=dat_struct['id'], fname=dat_struct['attributes']['name'])

		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, fname)

		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			content = self.wg.getpage(url, addlHeaders={"Referer" : "https://www.patreon.com/home"})
			if content:
				if isinstance(content, str):
					with open(fqpath, "wb") as fp:
						fp.write(content.encode("utf-8"))
				else:
					with open(fqpath, "wb") as fp:
						fp.write(content)
			else:
				return None

		return fqpath

	# TODO: Implement this
	def fetch_video_embed(self, post_content):
		return None

	def _getContentUrlFromPage(self, soup):

		dlBar = soup.find('ul', id='detail-actions')


		dummy, dlLink, dummy = dlBar.find_all('li')
		if 'Download' in dlLink.get_text():
			itemUrl = urllib.parse.urljoin(self.urlBase, dlLink.a['href'])

			return itemUrl

		raise ValueError("Wat?")


	def _getArtPage(self, postId, artistName):


		post = self.get_json("/posts/{pid}".format(pid=postId), apikey=True)


		attachments = {item['id'] : item for item in post['included'] if item['type'] == 'attachment'}

		print("Attachments:")

		post_content = post['data']
		post_info = post_content['attributes']

		tags = []
		if 'user_defined_tags' in post_content['relationships']:
			for tagmeta in post_content['relationships']['user_defined_tags']['data']:
				tags.append(tagmeta['id'].split(";")[-1])

		# pprint.pprint(post_content['relationships'])

		ret = {
			'page_desc'  : post_info['content'],
			'page_title' : post_info['title'],
			'post_time'  : dateutil.parser.parse(post_info['published_at']),
			'post_tags'  : tags,
		}


		files = []
		try:
			if "post_file" in post_content and post_content['post_file']:
				fpath = self.save_image(artistName, postId, post_content['post_file']['name'], post_content['post_file']['url'])
				files.append(fpath)

			if 'post_type' in post_content and post_content['post_type'] == 'video_embed':
				fpath = self.fetch_video_embed(post_content)
				files.append(fpath)

			for aid, dat_struct in attachments.items():
				fpath = self.save_attachment(artistName, postId, dat_struct)
				files.append(fpath)

		except urllib.error.URLError:
			self.log.error("Failure retreiving content from post: %s", post)

		files = [filen for filen in files if filen]
		ret['dl_path'] = files
		ret['status']  = 'Succeeded'

		# pprint.pprint(ret)
		return ret

	def _load_art(self, campaign_id, artist_raw):

		artPages = self.get_campaign_posts(campaign_id)

		aid = self._artist_name_to_rid(artist_raw)

		self.log.info("Total gallery items %s", len(artPages))

		new = 0
		with self.db.context_sess() as sess:
			for item in artPages:
				new += self._upsert_if_new(sess, aid, item)

		self.log.info("%s new art pages, %s total", new, len(artPages))

		# oldArt = self._getPreviouslyRetreived(artist)
		# newArt = artPages - oldArt
		# self.log.info("Old art items = %s, newItems = %s", len(oldArt), len(newArt))

		return self._getNewToRetreive(aid=aid)

	def getArtist(self, artist_undecoded, ctrlNamespace):
		artist_decoded = json.loads(artist_undecoded)
		patreon_aid, artist_meta = artist_decoded
		artist_name, artist_meta = artist_meta

		if ctrlNamespace.run is False:
			self.log.warning("Exiting early from %s due to run flag being unset", artist_undecoded)
			return True

		try:
			self.log.info("GetArtist - %s -> %s", artist_name, artist_undecoded)
			self.setupDir(artist_name)

			if 'campaign' in artist_meta and artist_meta['campaign']['data']['type'] == 'campaign':
				campaign_id = artist_meta['campaign']['data']['id']

				newArt = self._load_art(campaign_id, artist_undecoded)
			else:
				newArt = []

			while len(newArt) > 0:
				postid = newArt.pop()
				try:
					ret = self._fetch_retrier(postid, artist_name)

					assert isinstance(ret, dict)
					assert 'status'     in ret
					assert 'dl_path'    in ret
					assert 'page_desc'  in ret
					assert 'page_title' in ret
					assert 'post_time'  in ret
					assert 'post_tags'  in ret


					if ret['status'] == "Succeeded" or ret['status'] == "Exists":
						assert isinstance(ret['dl_path'], list)
						seq = 0
						for item in ret['dl_path']:
							self._updatePreviouslyRetreived(
									artist=artist_undecoded,
									state='complete',
									release_meta=postid,
									fqDlPath=item,
									pageDesc=ret['page_desc'],
									pageTitle=ret['page_title'],
									seqNum=seq,
									addTime=ret['post_time'],
									postTags=ret['post_tags'],
								)
							seq += 1
					elif ret['status'] == "Ignore":  # Used for compound pages (like Pixiv's manga pages), where the page has multiple sub-pages that are managed by the plugin
						self.log.info("Ignoring root URL, since it has child-pages.")
					else:
						self._updateUnableToRetrieve(artist_undecoded, postid)

				except urllib.error.URLError:  # WebGetRobust throws urlerrors
					self.log.error("Page Retrieval failed!")
					self.log.error("PostID = '%s'", postid)
					self.log.error(traceback.format_exc())
				except:
					self.log.error("Unknown error in page retrieval!")
					self.log.error("PostID = '%s'", postid)
					self.log.error(traceback.format_exc())


				self.log.info("Pages for %s remaining = %s", artist_name, len(newArt))
				if ctrlNamespace.run is False:
					break

			self._updateLastFetched(artist_undecoded)
			self.log.info("Successfully retreived content for artist %s", artist_name)

			return False
		except:
			self.log.error("Exception when retreiving artist %s", artist_name)
			self.log.error("%s", traceback.format_exc())
			return True



	# 	raise RuntimeError("How did this ever execute?")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def get_artist_lut(self):
		general_meta = self.current_user_info()
		campaign_items = [item for item in general_meta['included'] if item['type'] == "campaign"]
		artist_lut = {item['id'] : (item['attributes']['full_name'], item['relationships']) for item in general_meta['included'] if item['type'] == 'user'}

		return artist_lut

	def getNameList(self):
		self.getCookie()

		self.log.info("Getting list of favourite artists.")

		artist_lut = self.get_artist_lut()

		self.log.info("Found %d Names", len(artist_lut))
		for key, value in artist_lut.items():
			print((key, value))

		resultList = [json.dumps((key, value)) for key, value in artist_lut.items()]
		# Push the pixiv name list into the DB
		with self.db.context_sess() as sess:
			for name in resultList:
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.targetShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name)              \
					.scalar()
				if not res:
					self.log.info("Need to insert name: %s", name)
					sess.add(self.db.ScrapeTargets(site_name=self.targetShortName, artist_name=name))
					sess.commit()


		return super().getNameList()







	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_campaign_posts(self, cid, count=10):
		now = datetime.datetime.utcnow().replace(tzinfo = pytz.utc).replace(microsecond=0)

		postids = set()
		while 1:
			current = self.get_json("/campaigns/{cid}/posts?filter[is_by_creator]=true&page[count]={count}&use-defaults-for-included-resources=false".format(cid=cid, count=count) +
				"&fields[post]=published_at" +
				"&page[cursor]={now}".format(now=str(now.isoformat())) +
				"&fields[post]=comment_count&json-api-version=1.0", apikey=False)

			had_post = False
			for post in current['data']:
				if post['type'] != "post":
					continue
				postdate = dateutil.parser.parse(post['attributes']['published_at'])
				postid   = post['id']

				if postdate < now:
					now = postdate
				if not postid in postids:
					postids.add(postid)
					had_post = True

			if not had_post:
				break

		return postids



	def run_old(self):
		self.check_login()
		# self.get_pledges()
		self.fetch_all()



if __name__ == '__main__':

	import multiprocessing.managers
	import logSetup
	logSetup.initLogging()

	manager = multiprocessing.managers.SyncManager()
	manager.start()
	namespace = manager.Namespace()
	namespace.run=True


	ins = GetPatreon()
	# nl = ins.checkCookie()
	# nl = ins.getCookie()
	# nl = ins.getNameList()

	ins.go(ctrlNamespace=namespace)

	# print(nl)
	# print(ins)
	# print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	# ins.getArtist('["191466", ["Dan Shive", {"campaign": {"links": {"related": "https://www.patreon.com/api/campaigns/96494"}, "data": {"type": "campaign", "id": "96494"}}}]]', 'testtt')

	# ins._fetch_retrier(13131994, "Dan Shive")
	# ins.getArtist('["191466", ["Dan Shive", {"campaign": {"links": {"related": "https://www.patreon.com/api/campaigns/96494"}, "data": {"type": "campaign", "id": "96494"}}}]]', namespace)

	# nl = ins.getNameList()

	# for artist in nl:
	# 	print(artist)
	# print(nl)


