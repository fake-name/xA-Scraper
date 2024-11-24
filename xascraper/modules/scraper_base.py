
import os
import os.path
import traceback
import concurrent.futures
import time
import datetime
import urllib.error
import abc
import mimetypes
import pickle
import random
import tqdm
import magic
import WebRequest
import sqlalchemy.exc
from settings import settings

from xascraper.modules import module_base
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

def insertExtIfNeeded(fqFName, file_bytes):
	root, ext = os.path.splitext(fqFName)
	mime = magic.from_buffer(file_bytes, mime=True)
	should_ext = mimetypes.guess_extension(mime)
	if ext != should_ext and should_ext:
		if should_ext in ('.jpe', '.jpeg', '.jfif'):
			should_ext = '.jpg'
		if should_ext in ('.mp2', ):
			should_ext = '.mp3'
		return root + should_ext
	return fqFName


def insertCountIfFileExistsAndIsDifferent(fqFName, file_bytes):

	# If the file exists, check if we've already fetched it.
	if os.path.exists(fqFName):
		with open(fqFName, "rb") as fp:
			if fp.read() == file_bytes:
				return fqFName

	base, ext = os.path.splitext(fqFName)
	loop = 1
	while os.path.exists(fqFName):
		fqFName = "%s - (%d)%s" % (base, loop, ext)
		if os.path.exists(fqFName):
			with open(fqFName, "rb") as fp:
				if fp.read() == file_bytes:
					return fqFName

		loop += 1

	return fqFName


def prep_check_fq_filename(fqfilename):
	fqfilename = os.path.abspath(fqfilename)



	filepath, fileN = os.path.split(fqfilename)
	fileN = makeFilenameSafe(fileN)

	filepath = filepath.replace(":", "")

	# Create the target container directory (if needed)
	if not os.path.exists(filepath):
		os.makedirs(filepath, exist_ok=True)    # Hurray for race conditions!

	assert os.path.isdir(filepath)

	fqfilename = os.path.join(filepath, fileN)

	return fqfilename


class ScraperBase(module_base.ModuleBase, metaclass=abc.ABCMeta):

	# Abstract class (must be subclassed)
	__metaclass__ = abc.ABCMeta

	def __init__(self):
		print("ScraperBase Init")
		assert self.pluginShortName in settings, "Plugin short key ('%s') not in settings file!" % (self.pluginShortName)
		self.dlBasePath = settings[self.pluginShortName]["dlDirName"]
		self.config_file_name = "transient_config.pik"

		super().__init__()


	@classmethod
	def validate_config(cls, params):
		if cls.pluginShortName not in params:
			# print("No settings for plugin key %s. Skipping" % cls.pluginShortName)
			return None

		this_settings = params[cls.pluginShortName]

		assert 'username' in this_settings,    "Settings for plugin '%s' must have key 'username', which is missing!" % (cls.pluginShortName)
		assert 'password' in this_settings,    "Settings for plugin '%s' must have key 'password', which is missing!" % (cls.pluginShortName)
		assert 'runInterval' in this_settings, "Settings for plugin '%s' must have key 'runInterval', which is missing!" % (cls.pluginShortName)
		assert 'dlDirName' in this_settings,   "Settings for plugin '%s' must have key 'dlDirName', which is missing!" % (cls.pluginShortName)

		if not this_settings['runInterval']:
			# print("Plugin %s disabled (runInterval is false)" % (cls.pluginShortName))
			return False

		return True

	@classmethod
	def get_config(cls, params):
		if cls.pluginShortName not in params:
			# print("No settings for plugin key %s. Skipping" % cls.pluginShortName)
			return False

		this_settings = params[cls.pluginShortName]
		return cls, this_settings['runInterval'], cls.pluginShortName

	@abc.abstractmethod
	def pluginShortName(self):
		return None



	ovwMode = "Check Files"

	numThreads = 2

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Cookie Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	@abc.abstractmethod
	def checkCookie(self):
		pass

	@abc.abstractmethod
	def getCookie(self):
		pass


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Individual page scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	@abc.abstractmethod
	def _getArtPage(self, dlPathBase, artPageUrl, artistName):
		pass


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	@abc.abstractmethod
	def _getTotalArtCount(self, aid):
		pass

	@abc.abstractmethod
	def _getGalleries(self, artist):
		pass

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Overridable delay facility
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def post_delay(self):
		pass


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Utility
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------


	def random_sleep(self, start, mid, stop, include_long=True):

		sleeptime = random.triangular(start, mid, stop)

		# 1 in 10 chance of longer sleep
		if random.randrange(0, 10) == 0 and include_long:
			sleeptime = random.triangular(start*60, mid*60, stop*60)

		self.log.info("Sleeping %0.2f seconds", sleeptime)
		if sleeptime < 10:
			for _ in range(int(sleeptime)):
				time.sleep(1)
		else:
			for _ in tqdm.trange(int(sleeptime)):
				time.sleep(1)


		# Remaining sleep. Protbably silly.
		time.sleep(sleeptime % 1.0)


	def get_param_cache(self):
		if not os.path.exists(self.config_file_name):
			return {}

		with open(self.config_file_name, "rb") as fp:
			conf = pickle.load(fp)

		return conf.get(self.pluginShortName, {})


	def set_param_cache(self, value):
		conf = {}
		if os.path.exists(self.config_file_name):
			with open(self.config_file_name, "rb") as fp:
				conf = pickle.load(fp)

		conf[self.pluginShortName] = value

		with open(self.config_file_name, "wb") as fp:
			pickle.dump(conf, fp)



	def build_page_ret(self, status, fqDlPath, pageDesc=None, pageTitle=None, postTime=None, postTags=None, content_structured=None):

		assert isinstance(fqDlPath, (list, type(None))), "Wat? Item: %s, type: %s" % (fqDlPath, type(fqDlPath))
		assert status in ['Succeeded', 'Exists', 'Ignore', 'Failed', 'Deleted', 'Prose'], "Invalid status field: '%s'" % status
		assert isinstance(pageDesc,  (str, type(None))), "Wat? Item: %s, type: %s" % (pageDesc,  type(pageDesc))
		assert isinstance(pageTitle, (str, type(None))), "Wat? Item: %s, type: %s" % (pageTitle, type(pageTitle))

		if postTime:
			assert postTime < datetime.datetime.now() + datetime.timedelta(hours=24), "Item too far in the future " \
				"(%s > %s)!" % (postTime, datetime.datetime.now() + datetime.timedelta(hours=24))

		if pageTitle:
			pageTitle = pageTitle.strip()
		if pageDesc:
			pageDesc = pageDesc.strip()

		if fqDlPath:
			fqDlPath = [os.path.abspath(tmp) for tmp in fqDlPath if tmp]
			fqDlPath = [os.path.relpath(tmp, settings["dldCtntPath"]) for tmp in fqDlPath if tmp]


		ret = {
			'status'             : status,
			'dl_path'            : fqDlPath,
			'page_desc'          : pageDesc,
			'page_title'         : pageTitle,
			'post_time'          : postTime,
			'post_tags'          : set(postTags) if postTags else [],
			'content_structured' : content_structured,
		}

		return ret



	def save_file(self, fqfilename, file_content):

		fqfilename = prep_check_fq_filename(fqfilename)
		filepath, fileN = os.path.split(fqfilename)
		self.log.info("	Complete filepath: %s", fqfilename)

		chop = len(fileN)-4

		assert isinstance(file_content, (bytes, bytearray)), "save_file() requires the file_content be bytes! Passed %s" % file_content

		fqfilename = insertExtIfNeeded(fqfilename, file_content)
		fqfilename = insertCountIfFileExistsAndIsDifferent(fqfilename, file_content)



		while 1:
			try:
				with open(fqfilename, "wb") as fp:
					fp.write(file_content)

				return fqfilename

			except (IOError, OSError):
				chop = chop - 1

				if chop < 5:
					raise IOError("Cannot write to output file! This may be a permissions issue! Attempted filename: " +
						"'%s'. If you do not have disk permissions problems, please report this on github!" % (fqfilename, ))

				filepath, fileN = os.path.split(fqfilename)

				fileN = fileN[:chop]+fileN[-4:]
				self.log.warning("Truncating file length to %s characters and re-encoding.", chop)
				fileN = fileN.encode('utf-8','ignore').decode('utf-8')
				fileN = makeFilenameSafe(fileN)
				fqfilename = os.path.join(filepath, fileN)
				fqfilename = insertCountIfFileExistsAndIsDifferent(fqfilename, file_content)


		return None

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# DB Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _artist_name_to_rid(self, aname):
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets.id)             \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.filter(self.db.ScrapeTargets.artist_name == aname)              \
				.one()
			return res[0]

	# Fetch the previously retrieved item URLs from the database.
	def _getPreviouslyRetreived(self, artist):
		aid = self._artist_name_to_rid(artist)
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ArtItem.release_meta) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.all()

			return set([item for sublist in res for item in sublist])

	def _getNewToRetreive(self, artist=None, aid=None):
		if aid is None:
			aid = self._artist_name_to_rid(artist)

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ArtItem.release_meta) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.state == 'new') \
				.all()

			tmp = set([item for sublist in res for item in sublist])

			# Sort the return, so we run in the same order in all cases.
			tmp = list(tmp)
			tmp.sort()

			return tmp

	def _getSiteToRetreive(self, site):

		with self.db.context_sess() as sess:

			artists = sess.query(self.db.ScrapeTargets.id)             \
				.filter(self.db.ScrapeTargets.site_name == site)       \
				.all()

			artist_list = [tmp[0] for tmp in artists]

			res = sess.query(
						self.db.ArtItem.id,
						self.db.ArtItem.artist_id,
						self.db.ArtItem.release_meta
					) \
				.filter(self.db.ArtItem.artist_id.in_(artist_list)) \
				.filter(self.db.ArtItem.state == 'new') \
				.all()


			# Sort the return, so we run in the same order in all cases.
			tmp = list(res)
			tmp.sort()

			return tmp



	# Insert recently retreived items into the database
	def _updatePreviouslyRetreived(self,
				artist,
				release_meta,
				state              = 'new',
				fqDlPath           = None,
				pageDesc           = None,
				pageTitle          = None,
				seqNum             = None,
				filename           = None,
				addTime            = None,
				postTags           = [],
				content_structured = None
			):

		if addTime and addTime > datetime.datetime.now():
			addtime = datetime.datetime.now()

		aid = self._artist_name_to_rid(artist)

		with self.db.context_sess() as sess:
			for loop_cnt in range(5):
				try:
					row = sess.query(self.db.ArtItem) \
						.filter(self.db.ArtItem.artist_id == aid) \
						.filter(self.db.ArtItem.release_meta == release_meta) \
						.scalar()
					if row:
						self.log.info("Updating Item %s -> %s (%s).", aid, release_meta, loop_cnt)

					else:
						self.log.info("Item %s -> %s not present in DB. Adding", aid, release_meta)
						row = self.db.ArtItem(
								state        = 'new',
								artist_id    = aid,
								release_meta = release_meta,
								fetchtime    = datetime.datetime.now(),
								addtime      = datetime.datetime.now() if addTime is None else addTime,
								title        = pageTitle,
								content      = pageDesc,
							)
						sess.add(row)
						sess.flush()

					if pageDesc and pageDesc != row.content:
						row.content = pageDesc
					if content_structured and content_structured != row.content_structured:
						row.content_structured = content_structured
					if pageTitle and pageTitle != row.title:
						row.title = pageTitle
					if addTime and addTime != row.addtime:
						row.addtime = addTime
					if state and state != row.state:
						row.state = state

					if fqDlPath:
						frow = sess.query(self.db.ArtFile) \
							.filter(self.db.ArtFile.item_id == row.id) \
							.filter(self.db.ArtFile.seqnum == seqNum) \
							.scalar()

						if frow:
							if frow.fspath != fqDlPath:
								self.log.error("Item already exists, but download path is changing?")
								self.log.error("Old path: '%s'", frow.fspath)
								self.log.error("New path: '%s'", fqDlPath)
								frow.fspath = fqDlPath
						else:
							frow = self.db.ArtFile(
									item_id  = row.id,
									seqnum   = seqNum,
									filename = filename,
									fspath   = fqDlPath,
								)
							sess.add(frow)

					for tag in postTags:
						trow = sess.query(self.db.ArtTags) \
							.filter(self.db.ArtTags.item_id == row.id) \
							.filter(self.db.ArtTags.tag == tag) \
							.scalar()
						if not trow:
							tnew = self.db.ArtTags(item_id=row.id, tag=tag)
							sess.add(tnew)

					sess.commit()

					return

				except sqlalchemy.exc.InvalidRequestError:
					print("InvalidRequest error!")
					sess.rollback()
					traceback.print_exc()
				except sqlalchemy.exc.OperationalError:
					print("InvalidRequest error!")
					sess.rollback()
				except sqlalchemy.exc.IntegrityError:
					print("Integrity error!")
					print("Args:")

					print("	artist: ", artist)
					print("	release_meta: ", release_meta)
					print("	fqDlPath: ", fqDlPath)
					print("	pageDesc: ", pageDesc)
					print("	pageTitle: ", pageTitle)
					print("	seqNum: ", seqNum)
					print("	filename: ", filename)
					print("	addTime: ", addTime)
					print("	postTags: ", postTags)
					print("	content_structured: ", content_structured)

					traceback.print_exc()
					sess.rollback()

				except TypeError as e:
					print("Exception?")
					import traceback
					traceback.print_exc()

					import IPython
					IPython.embed()

				except SystemExit:
					raise

				except KeyboardInterrupt:
					raise

	def _checkHaveUrl(self, artist, url):
		aid = self._artist_name_to_rid(artist)
		with self.db.context_sess() as sess:
			res = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.release_meta == url) \
				.filter(self.db.ArtItem.state == 'complete') \
				.count()
			print("Res:", res)
			return res

	def _upsert_if_new(self, sess, aid, url, content_structured=None):

		res = sess.query(self.db.ArtItem) \
			.filter(self.db.ArtItem.artist_id == aid) \
			.filter(self.db.ArtItem.release_meta == url) \
			.count()
		if not res:
			if content_structured:
				row = self.db.ArtItem(
						state              = 'new',
						artist_id          = aid,
						release_meta       = url,
						content_structured = content_structured,
					)
			else:
				row = self.db.ArtItem(
						state        = 'new',
						artist_id    = aid,
						release_meta = url,
					)

			sess.add(row)
			sess.commit()
			return 1
		else:
			return 0


	# Insert bad item into DB
	def _updateUnableToRetrieve(self, artist, errUrl, state='error'):

		aid = self._artist_name_to_rid(artist)


		with self.db.context_sess() as sess:

			row = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.artist_id == aid) \
				.filter(self.db.ArtItem.release_meta == errUrl) \
				.scalar()
			if not row:
				row = self.db.ArtItem(
						state        = state,
						artist_id    = aid,
						release_meta = errUrl,
						fetchtime    = datetime.datetime.now(),
						addtime      = datetime.datetime.now(),
					)
				sess.add(row)
				sess.commit()


	def update_last_fetched(self, artist, fetch_time = None, force = False):
		if fetch_time is None:
			fetch_time = datetime.datetime.now()

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets)                              \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.filter(self.db.ScrapeTargets.artist_name == artist)             \
				.one()
			if res.last_fetched is None or res.last_fetched < fetch_time:
				self.log.info("Setting last fetched date to %s (previously %s) for artist %s (site: %s)", fetch_time, res.last_fetched, artist, self.pluginShortName)
				res.last_fetched = fetch_time
				sess.commit()

			elif force:
				self.log.info("Force setting last fetched date to %s (previously %s) for artist %s (site: %s)", fetch_time, res.last_fetched, artist, self.pluginShortName)
				res.last_fetched = fetch_time
				sess.commit()



	def get_content_structured(self, url):
		# This should be on aid, release_meta, but release_meta is going to be unique enough that we can just query on that.
		with self.db.context_sess() as sess:

			res = sess.query(self.db.ArtItem) \
				.filter(self.db.ArtItem.release_meta == url) \
				.scalar()

			if res:
				return res.content_structured
			else:
				return None


	def get_last_fetched(self, artist):

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets) \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.filter(self.db.ScrapeTargets.artist_name == artist) \
				.one()
			ret = res.last_fetched
			sess.commit()
		return ret


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# FS Management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	# Prep download dir (if needed)
	def setupDir(self, artist):

		dirPath = self.getDownloadPath(self.dlBasePath, artist)
		if not os.path.exists(dirPath):
			try:
				os.makedirs(dirPath)
			except:
				self.log.error("Cannot Make working directory %s/. Do you have write Permissions?", dirPath)
				raise
		if os.path.isfile(dirPath):
			raise IOError("Download path exists, and is a file. Wat")

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Target management and indirection
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def getNameList(self):

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets) \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.filter(self.db.ScrapeTargets.enabled == True) \
				.order_by(self.db.ScrapeTargets.last_fetched) \
				.all()

			ret = [(row.id, row.artist_name) for row in res]
			sess.commit()

		self.log.info("Have %s targets to scrape!", len(ret))
		return ret

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Threading and task management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _load_art(self, artist):
		aid = self._artist_name_to_rid(artist)
		totalArt = self._getTotalArtCount(artist)
		artPages = self._getGalleries(artist)

		self.log.info("Site reports %s total art items, in %s pages", totalArt, len(artPages))

		if totalArt is None:
			self.log.info("Site does not support total art counts. Found total gallery items %s", len(artPages))
		elif totalArt > len(artPages):
			self.log.warning("May be missing art? Total claimed art items from front-page = %s, total gallery items %s", totalArt, len(artPages))
		elif totalArt < len(artPages):
			self.log.warning("Too many art pages found? Total claimed art items from front-page = %s, total gallery items %s.", totalArt, len(artPages))
		else:
			self.log.info("Total claimed art items from front-page = %s, total gallery items %s", totalArt, len(artPages))

		new = 0
		with self.db.context_sess() as sess:
			for item in artPages:
				new += self._upsert_if_new(sess, aid, item)

		self.log.info("DB Updated with %s new art pages, %s total", new, len(artPages))

		ret = self._getNewToRetreive(artist)

		self.log.info("Have %s items that have not been retreived", len(ret))

		return ret

	def _fetch_retrier(self, *args, **kwargs):
		for _ in range(3):
			try:
				ret = self._getArtPage(*args, **kwargs)
				return ret
			except exceptions.ContentRemovedException as e:
				return self.build_page_ret(status="Failed", fqDlPath=None, pageTitle="ContentRemovedException Error: %s" % e)
			except exceptions.CannotAccessException as e:
				return self.build_page_ret(status="Failed", fqDlPath=None, pageTitle="CannotAccessException Error: %s" % e)
			except exceptions.CannotFindContentException as e:
				return self.build_page_ret(status="Failed", fqDlPath=None, pageTitle="CannotFindContentException Error: %s" % e)

			except exceptions.RetryException:
				time.sleep(random.triangular(1,3,10))
				self.checkCookie()

			except exceptions.NotLoggedInException:
				self.log.error("You are not logged in? Checking and re-logging in.")
				ok, message = self.getCookie()
				assert ok, "Failed to log in after NotLoggedInException!"


			except WebRequest.FetchFailureError as err:
				if err.err_code == 429:
					self.log.info("HTTP 429 Status, sleeping a bit and retrying.")
					self.random_sleep(5,10,15, include_long=False)
				else:
					raise

			except SystemExit:
				raise
			except KeyboardInterrupt:
				raise

			except Exception as e:

				print("Exception in _fetch_retrier: ", e)
				import traceback
				traceback.print_exc()

				# import IPython
				# IPython.embed()

		self.log.error("Failed to fetch content with args: '%s', kwargs: '%s'", args, kwargs)
		return self.build_page_ret(status="Failed", fqDlPath=None)

	def fetch_art_item(self, dlPathBase, pageURL, artist):

		valid_ret_keys = [
			'status',
			'dl_path',
			'page_desc',
			'page_title',
			'post_time',
			'post_tags',
			'content_structured',
		]

		try:
			ret = self._fetch_retrier(dlPathBase, pageURL, artist)

			assert isinstance(ret, dict)
			assert 'status'     in ret

			assert all([tmp in valid_ret_keys for tmp in ret.keys()]), "Invalid key in return. Allowed %s. Received %s (Bad: %s)" % (
				valid_ret_keys, list(ret.keys()), [tmp for tmp in ret.keys() if tmp not in valid_ret_keys])


			if ret['status'] == "Prose":
				assert 'dl_path'    in ret
				assert 'page_desc'  in ret
				assert 'page_title' in ret
				assert 'post_time'  in ret
				assert isinstance(ret['dl_path'], list)
				seq = 0
				self._updatePreviouslyRetreived(
						artist       = artist,
						state        = 'complete',
						release_meta = pageURL,
						fqDlPath     = None,
						pageDesc     = ret['page_desc'],
						pageTitle    = ret['page_title'],
						addTime      = ret['post_time'],
						postTags     = ret['post_tags'],
					)

			elif ret['status'] == "Succeeded" or ret['status'] == "Exists":
				assert 'dl_path'    in ret
				assert 'page_desc'  in ret
				assert 'page_title' in ret
				assert 'post_time'  in ret
				assert 'content_structured'  in ret
				assert isinstance(ret['dl_path'], list)

				# If we're not prose, we should have at least one file.
				assert ret['dl_path']

				seq = 0
				for item in ret['dl_path']:
					self._updatePreviouslyRetreived(
							artist             = artist,
							state              = 'complete',
							release_meta       = pageURL,
							fqDlPath           = item,
							pageDesc           = ret['page_desc'],
							pageTitle          = ret['page_title'],
							seqNum             = seq,
							addTime            = ret['post_time'],
							postTags           = ret['post_tags'],
							content_structured = ret['content_structured'],
						)
					seq += 1
			elif ret['status'] == "Ignore":  # Used for compound pages (like Pixiv's manga pages), where the page has multiple sub-pages that are managed by the plugin
				self.log.info("Ignoring root URL, since it has child-pages.")
			elif ret['status'] == 'Deleted':
				self._updateUnableToRetrieve(artist, pageURL, state='removed')
			else:
				self._updateUnableToRetrieve(artist, pageURL)

		except urllib.error.URLError:  # WebGetRobust throws urlerrors
			self.log.error("Page Retrieval failed!")
			self.log.error("Source URL = '%s'", pageURL)
			self.log.error(traceback.format_exc())


	def getArtist(self, artist, ctrlNamespace):


		if artist != artist.strip():
			artist = artist.strip()

			self.log.warning("Artist name seems to have trailing or leading whitespace!")

		if str(artist) == "0":
			print("Empty artist (or zero ID)")
			return False

		if ctrlNamespace.run is False:
			# self.log.warning("Exiting early from %s due to run flag being unset", artist)
			return True

		dlPathBase = self.getDownloadPath(self.dlBasePath, artist)


		try:
			self.log.info("GetArtist - %s", artist)
			self.setupDir(artist)

			newArt = self._load_art(artist)

			while len(newArt) > 0:
				pageURL = newArt.pop()
				self.fetch_art_item(dlPathBase, pageURL, artist)

				self.log.info("Pages for %s remaining = %s", artist, len(newArt))

				if ctrlNamespace.run is False:
					break

			self.update_last_fetched(artist)
			self.log.info("Successfully retreived content for artist %s", artist)

			self.post_delay()
			return False
		except exceptions.RetryException:
			self.log.error("Cannot consume. Will retry next execution")
			return False
		except exceptions.AccountDisabledException as err:
			self.log.error("Artist seems to have disabled their account: %s", err)
			self.update_last_fetched(artist)
			return False
		except WebRequest.FetchFailureError:
			self.log.error("Failure fetching artist '%s' for site '%s'", artist, self.pluginShortName)
			return False
		except exceptions.NoArtException:
			self.log.warning("Artist has no art (yet)!")
			return False
		except exceptions.UnrecoverableFailureException:
			self.log.error("Unrecoverable exception!")
			self.log.error(traceback.format_exc())
			ctrlNamespace.run = False
			return True
		except exceptions.NotLoggedInException:
			self.log.error("Aborting due to logout?")
			self.log.error(traceback.format_exc())
			ctrlNamespace.run = False
			return True

		except SystemExit:
			raise
		except KeyboardInterrupt:
			raise

		except:
			self.log.error("Unhandled exception when retreiving artist %s", artist)
			self.log.error("Aborting fetch.")
			self.log.error("%s", traceback.format_exc())
			ctrlNamespace.run = False
			return True

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

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.info("Do not have login cookie. Retreiving one now.")
				cookieStatus, msg = self.getCookie()
				self.log.info("Login attempt status = %s (%s).", cookieStatus, msg)
				assert cookieStatus, "Login failed! Cannot continue!"

			haveCookie, dummy_message = self.checkCookie()
			if not haveCookie:
				self.log.critical("Failed to download cookie! Exiting!")
				return False

			if not nameList:
				nameList = self.getNameList()

			errored = False

			# Farm out requests to the thread-pool
			with concurrent.futures.ThreadPoolExecutor(max_workers=self.numThreads) as executor:

				future_to_url = {}
				for aId, aName in nameList:
					future_to_url[executor.submit(self.getArtist, aName, ctrlNamespace)] = aName

				for future in concurrent.futures.as_completed(future_to_url):
					# aName = future_to_url[future]
					res = future.result()
					if type(res) is not bool:
						raise RuntimeError("Future for plugin %s returned non-boolean value (%s). Function %s of class %s" % (self.pluginShortName, res, self.getArtist, self))
					errored  |= future.result()
					# self.log.info("Return = %s, aName = %s, errored = %s" % (res, aName, errored))

			if errored:
				self.log.warn("Had errors!")

			runTime = datetime.datetime.now()-startTime
			self.updateLastRunDuration(self.pluginShortName, runTime)

		finally:
			self.updateRunningStatus(self.pluginShortName, False)


	@classmethod
	def runScraper(cls, managedNamespace):
		instance = cls()
		instance.go(ctrlNamespace=managedNamespace)

