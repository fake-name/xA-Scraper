
import os
import os.path
import traceback
import datetime
import pytz
import dateutil.parser
import urllib.parse
import json
from settings import settings

import rewrite.modules.scraper_base

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

class GetPatreon(rewrite.modules.scraper_base.ScraperBase):

	settingsDictKey = "pat"

	pluginName = "PatreonGet"

	urlBase = "http://{user}.tumblr.com/"

	ovwMode = "Check Files"

	numThreads = 1



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

	def deserialize_from_db(self, meta_out):
		return json.loads(meta_out)

	def serialize_to_db(self, meta_in):
		return json.dumps(meta_in)

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

	def user_info(self, uid):
		current = self.get_json("/user/{uid}".format(uid=uid), apikey=True)
		pprint.pprint(current)


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
		html_tags = "".join(["<div><ul class='tags'>"] +
			["<li>{tag}</li>".format(tag=tag) for tag in raw_tags] +
			["</ul></div>"])

		self._updatePreviouslyRetreived(artist=orga, release_meta=pgurl, pageDesc=desc+html_tags, pageTitle=title, postTags=raw_tags)

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

			# NFI how this was happening.
			if filePath.startswith("{"):
				filePath = filePath[1:]

			if isinstance(content, str):
				content = content.encode(encoding='UTF-8')

			with open(filePath, "wb") as fp:								# Open file for saving image (Binary)
				fp.write(content)						# Write Image to File

			self._updatePreviouslyRetreived(artist=orga, release_meta=pgurl, fqDlPath=filePath, seqNum=seq)
			seq += 1


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
			self.log.warning("Exiting early from %s due to run flag being unset", artist)
			return True

		dlPathBase = self.getDownloadPath(self.dlBasePath, artist_name)



		try:
			self.log.info("GetArtist - %s -> %s", artist_name, artist_undecoded)
			self.setupDir(artist_name)

			if 'campaign' in artist_meta and artist_meta['campaign']['data']['type'] == 'campaign':
				campaign_id = artist_meta['campaign']['data']['id']

				newArt = self._load_art(campaign_id, artist_undecoded)
			else:
				newArt = []

			print("artist:", (patreon_aid, artist_name, artist_meta, dlPathBase))
			return

			while len(newArt) > 0:
				postid = newArt.pop()
				try:
					ret = self.__fetch_retrier(dlPathBase, postid, artist_undecoded)

					assert isinstance(ret, dict)
					assert 'status'     in ret
					assert 'dl_path'    in ret
					assert 'page_desc'  in ret
					assert 'page_title' in ret
					assert 'post_time'  in ret


					if ret['status'] == "Succeeded" or ret['status'] == "Exists":
						assert isinstance(ret['dl_path'], list)
						seq = 0
						for item in ret['dl_path']:
							self._updatePreviouslyRetreived(
									artist=artist_decoded,
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
						self._updateUnableToRetrieve(artist_undecoded, pageURL)

				except urllib.error.URLError:  # WebGetRobust throws urlerrors
					self.log.error("Page Retrieval failed!")
					self.log.error("Source URL = '%s'", pageURL)
					self.log.error(traceback.format_exc())
				except:
					self.log.error("Unknown error in page retrieval!")
					self.log.error("Source URL = '%s'", pageURL)
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








	def _getGalleries(self, artist):

		posts = self.get_user_posts()
		# artlinks = set()
		# artist = artist.strip()

		# baseUrl = self.urlBase.format(user=artist)

		# posts = []
		# offset = 0
		# step   = 20
		# while 1:
		# 	self.log.info("Fetching posts at offset: %s for user %s", offset, artist)
		# 	addposts = self.t.get('posts', blog_url=baseUrl, params={"limit" : step, 'offset':offset})
		# 	offset += step
		# 	if len(addposts['posts']) == 0:
		# 		break
		# 	posts.extend(addposts['posts'])

		# self.log.info("Found %s links" % (len(posts)))
		# return posts

	def _getTotalArtCount(self):
		pass




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_campaign(self, cid):
		current = self.get_json("/campaigns/{cid}".format(cid=cid), apikey=True)
		# pprint.pprint(current)

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

	def get_user(self, uid):
		current = self.get_json("/user/{uid}".format(uid=uid), apikey=True)
		pprint.pprint(current)

	def get_posts(self):
		current = self.get_json("/stream?page=2")
		posts = [item for item in current['data'] if item['type'] == "post"]

		pprint.pprint(current)
		print("Posts:", len(posts))


	# def get_campaign_posts(self, cid):
	# 	current = self.get_json("/campaigns/{cid}/posts?p=0".format(cid=cid))
	# 	posts = [item for item in current['data'] if item['type'] == "post"]

		# pprint.pprint(current)
	# 	print("Posts:", len(posts))


	def get_user_posts(self, uid):
		page = 1
		addlHeaders={
			"Referer"          : "https://www.patreon.com/home",
			"X-Requested-With" : "XMLHttpRequest",
			}
		item_count = 0
		posts = []
		while 1:
			container = self.wg.getSoup("https://www.patreon.com/userNext?p={page}&ty=c&u={uid}".format(uid=uid, page=page), addlHeaders=addlHeaders)

			items = container.find_all("div", class_='box')
			posts += items
			item_count += len(items)
			print("Found %s items on page. Total so far: %s " % (len(items), item_count))
			if len(items) == 0:
				break
			page += 1
		return posts

	def get_save_dir(self, aname):
		dirp = os.path.join(settings.SAVE_DIR, aname)
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

	# TODO: Implement this
	def fetch_video_embed(self, post_content):
		pass

	def fetch_post(self, pid, aname):
		post = self.get_json("/posts/{pid}".format(pid=pid), apikey=True)


		attachments = {item['id'] : item for item in post['included'] if item['type'] == 'attachment'}


		post_content = post['data']
		# pprint.pprint(post_content)
		try:
			if "post_file" in post_content and post_content['post_file']:
				self.save_image(aname, pid, post_content['post_file']['name'], post_content['post_file']['url'])

			if 'post_type' in post_content and post_content['post_type'] == 'video_embed':
				self.fetch_video_embed(post_content)

			for aid, dat_struct in attachments.items():
				self.save_attachment(aname, pid, dat_struct)
		except urllib.error.URLError:
			self.log.error("Failure retreiving content from post: %s", post)

		self.save_json(aname, pid, post)


		# pprint.pprint(includeLut)

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
	# print(nl)
	# print(ins)
	# print("Instance: ", ins)
	# dlPathBase, artPageUrl, artistName
	# ins.getArtist('["191466", ["Dan Shive", {"campaign": {"links": {"related": "https://www.patreon.com/api/campaigns/96494"}, "data": {"type": "campaign", "id": "96494"}}}]]', 'testtt')

	ins.getArtist('["191466", ["Dan Shive", {"campaign": {"links": {"related": "https://www.patreon.com/api/campaigns/96494"}, "data": {"type": "campaign", "id": "96494"}}}]]', namespace)

	# nl = ins.getNameList()

	# for artist in nl:
	# 	print(artist)
	# print(nl)


