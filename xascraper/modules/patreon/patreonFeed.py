import os
import os.path
import traceback
import datetime
import time
import pytz
import dateutil.parser
import bs4
import WebRequest
import cloudscraper
import urllib.parse
import json
import time
import random
import pprint
import requests
import ChromeController
from settings import settings

import xascraper.modules.scraper_base
from xascraper.modules import exceptions

from . import patreonBase

class LoginFailure(Exception):
	pass

class FetchError(Exception):
	pass

PATREON_LOGIN_PAGE = 'https://www.patreon.com/login'
PATREON_HOME_PAGE  = 'https://www.patreon.com/home'

def extract_image_fn(url):
	parsed = urllib.parse.urlparse(url)
	return parsed.path.split("/")[-1]

class GetPatreonFeed(patreonBase.GetPatreonBase):

	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Process following page
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def build_and_upsert_follows(self, member_dict, campaign_dict):
		'''
		Items in the name-list for patreon look like the following, where
		the first number is the row ID, and the second is the "artist name", which is actually a json string in the name column in the DB

			[
				158019,
				"[\"Jeph Jacques\", {\"campaign\": {\"data\": {\"id\": \"94958\", \"type\": \"campaign\"}, \"links\": {\"related\": \"https://www.patreon.com/api/campaigns/94958\"}}}]"
			],
		'''

		arts = [(campaign_dict[item['campaign']['data']['id']]['name'], item) for item in member_dict.values()]

		resultList = [(json.dumps(tmp, sort_keys=True), tmp) for tmp in arts]

		ret = {}

		with self.db.context_sess() as sess:
			for name_str, obj in resultList:
				res = sess.query(self.db.ScrapeTargets.id)             \
					.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
					.filter(self.db.ScrapeTargets.artist_name == name_str)              \
					.scalar()

				ret[obj[1]['campaign']['data']['id']] = (name_str, obj[1])

				if not res:
					self.log.info("Need to insert name: %s", name_str)
					sess.add(self.db.ScrapeTargets(site_name=self.pluginShortName, artist_name=name_str))
					sess.commit()
				else:
					self.log.info("Have campaign: %s", name_str)

		with self.db.context_sess() as sess:
			res = sess.query(self.db.ScrapeTargets)             \
				.filter(self.db.ScrapeTargets.site_name == self.pluginShortName) \
				.all()

			for row in res:
				row.enabled = True

				# if row.artist_name in resultList:
				# 	if not row.enabled:
				# 		self.log.info("Enabling artist: %s", row.artist_name)
				# 		row.enabled = True
				# else:
				# 	if row.enabled:
				# 		self.log.info("Disabling artist: %s", row.artist_name)
				# 		row.enabled = False

			sess.commit()

		return ret

	def get_recent_feed(self, cr):
		url = "https://www.patreon.com/notifications?mode=user"

		navs = {}
		def closure(container, url, content, meta):
			navs[url] = {
				'url' : url,
				'content' : content,
				'meta' : meta,
			}

		def filt(url, meta):
			return "www.patreon.com" in url.lower()

		cr.set_filter_func(filt)
		cr.install_listener_for_content(closure)

		cr.blocking_navigate(url)

		for _ in range(5):
			cr.drain_transport()
			time.sleep(1)


		watch_list_obj = 'https://www.patreon.com/api/notif-feed?include=notifs&filter[mode]=member&json-api-version=1.0&json-api-use-default-includes=false'
		member_list_obj = 'https://www.patreon.com/api/current_user?include=active_memberships.campaign&fields[campaign]=avatar_photo_image_urls%2Cname%2Cpublished_at%2Curl%2Cvanity%2Cis_nsfw&fields[member]=is_free_member%2Cis_free_trial&json-api-version=1.0&json-api-use-default-includes=false'

		cr.set_filter_func(None)
		cr.remove_all_handlers()
		cr.clear_content_listener_cache()
		cr.Log_clear()

		if watch_list_obj not in navs:
			raise exceptions.UnrecoverableFailureException("Did not receive list of recent notifications. Check if something has changed!")


		if member_list_obj not in navs:
			raise exceptions.UnrecoverableFailureException("Did not receive list of memberships. Check if something has changed!")

		ctnts = navs[watch_list_obj]["content"]
		ctnt  = json.loads(ctnts)
		mbss  = navs[member_list_obj]["content"]
		mbs   = json.loads(mbss)

		with open("navs.pyson", "w") as fp:
			for key, value in navs.items():
				fp.write("\n\nObject: '%s'\n" % (key, ))

				pprint.pp(value, fp, width=140, sort_dicts=True)


		incl = mbs['included']
		member_dict = {item['id'] : item['relationships'] for item in incl if item['type'] == 'member'}
		campaign_dict = {item['id'] : item['attributes'] for item in incl if item['type'] == 'campaign'}


		db_name_items = self.build_and_upsert_follows(member_dict, campaign_dict)


		return db_name_items, member_dict, campaign_dict, ctnt

	def process_feed_items(self, cr, db_name_items, member_dict, campaign_dict, ctnt):
		items = ctnt['included']
		self.log.info("Processing recent item feed containing %s items", len(items))

		new = 0
		upd = 0
		skp = 0
		ign = 0
		for item in items:
			# Skip attempts to upsell
			if 'for_sale_intent' in item['id']:
				ign += 1
				continue
			# Don't care
			if 'member_like' in item['id']:
				ign += 1
				continue

			# The desired release-meta string for a item is something like '["post", "1272472"]'. Patreon consistently sends the post IDs as strings, so that should be maintained.
			# The main challenge here is getting back to the relevant campaign from the post, since it's not freaking mentioned anywhere.
			# Post IDs seem to be globally unique, and can be turned into a corresponding URL as "https://patreon.com/posts/{post_id}"

			post_id = item['id']
			prof_img = item['attributes']['profile_image_url']

			if not post_id.startswith("new_post::"):
				self.log.info("Not a 'new_post::' item: ", post_id)
				import pdb
				pdb.set_trace()

			item_meta = '["post", "{num}"]'.format(num=post_id.split(":")[-1])

			if not "/campaign/" in prof_img:
				import pdb
				pdb.set_trace()

			_, val = prof_img.split("/campaign/")
			camp_id = val.split("/")[0]

			assert camp_id in db_name_items

			try:
				artist_str, _ = db_name_items[camp_id]
				loc_a_id = self._artist_name_to_rid(artist_str)

			except:
				self.log.info("Did not have campaign: '%s'" % (db_name_items[camp_id], ))
				traceback.print_exc()

				import pdb
				pdb.set_trace()

			with self.db.context_sess() as sess:
				# This is /slightly/ different from the logic of self._upsert_if_new(), since we
				# don't bother also cross-referencing by aid, and we do date-based invalidation.
				res = sess.query(self.db.ArtItem) \
					.filter(self.db.ArtItem.release_meta == item_meta) \
					.scalar()
				if res:
					# Re-fetch if it's been updated since we fetched it.
					last_update = dateutil.parser.parse(item['attributes']['updated_at']).replace(tzinfo=None)
					if last_update > res.fetchtime and res.state != 'new':
						res.state = 'new'
						sess.commit()
						upd += 1
					else:
						skp += 1

					# Check we're not bugged out (artist should be fixed)
					assert res.artist_id == loc_a_id

				else:
					row = self.db.ArtItem(
							state              = 'new',
							artist_id          = loc_a_id,
							release_meta       = item_meta,
							content_structured = item,
						)

					sess.add(row)
					sess.commit()
					new += 1

		self.log.info("Finished processing feed, with %s new, %s updated, and %s existing items. Skipped %s items", new, upd, skp, ign)

	def fetch_and_insert_new(self, cr):

		db_name_items, member_dict, campaign_dict, ctnt = self.get_recent_feed(cr)

		# member_dict:   opaque_guid -> (some) campaign metadata
		# campaign_dict: campaign_id -> campaign metadata
		# ctnt:          raw watch content

		self.process_feed_items(cr, db_name_items, member_dict, campaign_dict, ctnt)


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Retreival functions for each post
	# This expects to be able to manipulate the underlying chrome instance.
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------



	def get_save_dir(self, aname):

		dirp = self.getDownloadPath(self.dlBasePath, aname)
		if not os.path.exists(dirp):
			os.makedirs(dirp)
		return dirp

	def local_save_file(self, aname, filename, filecontent):
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, filename)
		self.save_file(fqfilename=fqpath, file_content=filecontent)

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
		self.log.info("Saving image: '%s'", furl)
		fname = "{pid}-{fname}".format(pid=pid, fname=fname)
		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, fname)
		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			try:
				content = self.fetch_with_chrome(self.cr, furl)
			except WebRequest.FetchFailureError:
				self.log.error(traceback.format_exc())
				self.log.error("Could not retreive content: ")
				self.log.error("%s", furl)
				return None

			if content:
				self.local_save_file(aname, fname, content)
			else:
				self.log.error("Could not retreive content: ")
				self.log.error("%s", furl)
				return None
		return fqpath


	def save_media(self, aname, pid, dat_struct):
		self.log.info("Saving media item: '%s'", dat_struct['attributes']['download_url'])
		if dat_struct['attributes']['download_url'].startswith("https"):
			url = dat_struct['attributes']['download_url']
		else:
			url = "https:{url}".format(url=dat_struct['attributes']['download_url'])


		fname = str(dat_struct['attributes']['file_name']).rsplit("/", maxsplit=1)[-1]
		fname = "{pid}-{aid}-{fname}".format(pid=pid, aid=dat_struct['id'], fname=fname)

		fdir = self.get_save_dir(aname)
		fqpath = os.path.join(fdir, fname)

		if os.path.exists(fqpath):
			self.log.info("Do not need to download: '%s'", fname)
		else:
			try:
				content = self.fetch_with_chrome(self.cr, url)
			except WebRequest.FetchFailureError:
				self.log.error(traceback.format_exc())
				self.log.error("Could not retreive content: ")
				self.log.error("%s", url)
				return None
			if content:
				if isinstance(content, str):
					self.local_save_file(aname, fname, content.encode("utf-8"))
				else:
					self.local_save_file(aname, fname, content)
			else:
				return None

		return fqpath



	# TODO: Implement this
	def fetch_video_embed(self, post_content):
		self.log.warning("Embedded video. Plz complain on github about this!")
		return None

	def _handle_embed(self, embed_info):
		self.log.warning("Embedded external content. Plz complain on github about this!")
		self.log.warning("Include the above json-like output so I can see what I need to do.")
		return []



	def __handle_errors(self, post_errors):
		for error in post_errors:
			if 'code_name' in error and error['code_name'] == 'ResourceMissing' and 'status' in error and error['status'] == '404':
				raise exceptions.ContentRemovedException("Item has been deleted or removed.")


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def inject_link_and_click(self, cr, link_url):


		cr.execute_javascript_statement("""
		( function do_nav()
		{
			var link = document.createElement("a");
			link.href = "%s";
			link.click();
			return link;
		})()
		""" % (link_url, ))

	def do_fetch_item(self, item_row):
		self.log.info("Doing fetch for item: %s", item_row)

		item_id, artist_id, release_meta = item_row
		meta_loaded = json.loads(release_meta)
		post_id = meta_loaded[-1]
		tgt_url = "https://www.patreon.com/posts/{post_id}".format(post_id=post_id)

		self.log.info("Navigating to %s", tgt_url)
		artistName, _ = self._rid_to_artist_json(artist_id)

		self.inject_link_and_click(self.cr, tgt_url)

		for _ in range(5):
			self.cr.drain_transport()
			time.sleep(1)


		script_ctnt = self.cr.execute_javascript_statement('document.getElementById("__NEXT_DATA__").innerHTML')
		assert script_ctnt['type'] == 'string'

		item_ctnt = json.loads(script_ctnt['value'])

		try:
			# So pinned ("featured") posts are fiddly here, in that they redirect to the campaign page.
			# We therefore have to handle the case where theres no 'post' member in the bootstrap blob.
			# From the way the json is structured, I think there can only ever be one featured post.
			bootstrap = item_ctnt['props']['pageProps']['bootstrapEnvelope']['pageBootstrap']

			if 'post' in bootstrap:
				post = bootstrap['post']
			else:
				post = bootstrap['featuredPost']


		except KeyError:
			self.log.info("Missing bootstrap envelope to parse!")
			# pprint.pprint(item_ctnt)
			import pdb
			pdb.set_trace()



		if not 'data' in post:
			if "errors" in post:
				self.__handle_errors(post['errors'])

			self.log.warning("No 'data' member in post!")

			pprint.pprint(post)
			fail = {
				'status' : ''
				}
			return fail


		post_content = post['data']
		post_info = post_content['attributes']

		if 'current_user_can_view' in post_info and post_info['current_user_can_view'] is False:
			self.log.warning("You apparently cannot view post %s for artist %s. Ignoring.", item_id, artistName)
			fail = {
				'status' : ''
				}
			return fail

		if not 'included' in post:
			self.log.warning("No contents on post %s for artist %s (%s). Please report if this is in error.", item_id, artistName, post_info['url'])
			fail = {
				'status' : ''
				}
			return fail

		# Thiese are mostly unused. For debugging user only
		media       = {item['id'] : item for item in post['included'] if item['type'] == 'media'}

		access_rule	= {item['id'] : item for item in post['included'] if item['type'] == 'access-rule'}
		campaign    = {item['id'] : item for item in post['included'] if item['type'] == 'campaign'}
		comment     = {item['id'] : item for item in post['included'] if item['type'] == 'comment'}
		pledge      = {item['id'] : item for item in post['included'] if item['type'] == 'pledge'}
		post_tag    = {item['id'] : item for item in post['included'] if item['type'] == 'post_tag'}
		reward      = {item['id'] : item for item in post['included'] if item['type'] == 'reward'}
		reward_item = {item['id'] : item for item in post['included'] if item['type'] == 'reward-item'}
		user        = {item['id'] : item for item in post['included'] if item['type'] == 'user'}

		tags = []
		if 'user_defined_tags' in post_content['relationships']:
			for tagmeta in post_content['relationships']['user_defined_tags']['data']:
				tags.append(tagmeta['id'].split(";")[-1])

		if 'current_user_can_view' in post_content and not post_content['current_user_can_view']:
			raise exceptions.CannotAccessException("You can't view that content!")

		# if not 'content' in post_info:
		# pprint.pprint(post_content)

		ret = {
			'page_desc'   : post_info['content'],
			'page_title'  : post_info['title'],
			'post_time'   : dateutil.parser.parse(post_info['published_at']).replace(tzinfo=None),
			'post_tags'   : tags,
			'post_embeds' : [],
		}


		attachments = {}
		shown_media = {}

		# Handle posts with the metadata tag present, but the metadata content set to None
		if 'post_metadata' in post_info and not post_info['post_metadata']:
			post_info['post_metadata'] = {}

		image_ids = post_info.get('post_metadata', {}).get('image_order', [])

		for itemid, item in media.items():
			if itemid in image_ids:
				shown_media[itemid] = item
			else:
				attachments[itemid] = item

		if post_info['post_type'] == 'image_file':
			pass
		elif post_info['post_type'] == 'text_only':
			pass
		elif post_info['post_type'] == 'audio_file':
			pass
		elif post_info['post_type'] == 'poll':
			# Don't care about polls
			pass

		elif post_info['post_type'] == 'video_embed':
			# Youtube, if not youtube short
			pass
		elif post_info['post_type'] == 'link':
			# Link posts use the "embed" field
			# I think this may also effectively subsume the youtube embeds
			pass

		else:
			self.log.warning("Unknown post type: %s", post_info['post_type'])

			import pdb
			pdb.set_trace()


		files = []
		try:
			if "post_file" in post_info and post_info['post_file']:

				furl = urllib.parse.unquote(post_info['post_file']['url'])
				# print("Post file!", post_info['post_file']['url'], furl)

				fn = post_info['post_file'].get('name', "{pid}-body_file-{fname}".format(pid=post_id, fname=extract_image_fn(furl)))

				fpath = self.save_image(artistName, item_id, fn , furl)
				files.append(fpath)

			# There's no real distinction between attachments and shown media.
			# The separation here is largely historical.
			for aid, dat_struct in attachments.items():
				# print("Post attachments")
				fpath = self.save_media(artistName, item_id, dat_struct)
				files.append(fpath)

			for aid, dat_struct in shown_media.items():
				# print("Post attachments")
				fpath = self.save_media(artistName, item_id, dat_struct)
				files.append(fpath)



			if 'embed' in post_info and post_info['embed']:

				for item in self._handle_embed(post_info['embed']):
					files.append(fpath)

				ret['post_embeds'].append(post_info['embed'])

				self.log.warning("Post embed that is not a video!")

			if 'post_type' in post_info and post_info['post_type'] == 'video_embed':
				# print("Post video_embed")
				fpath = self.fetch_video_embed(post_info)
				if fpath:
					files.append(fpath)

				ret['post_embeds'].append(post_info)
				self.log.warning("Post video_embed!")


		except urllib.error.URLError:
			self.log.error("Failure retreiving content from post: %s", post)

		# except:
		# 	print("General error fetching post!")
		# 	print(traceback.format_exc())
		# 	import pdb
		# 	pdb.set_trace()

		# Posts can apparently be empty.
		if not post_info['content']:
			post_info['content'] = ""

		ctnt_soup = bs4.BeautifulSoup(post_info['content'], 'lxml')

		for img in ctnt_soup.find_all("img", src=True):
			furl = img['src']
			fparsed = urllib.parse.urlparse(furl)
			fname = fparsed.path.split("/")[-1]

			# Somehow empty urls ("http://") are getting into here.
			if len(furl) > len("https://xx"):
				fpath = self.save_image(artistName, item_id, fname, furl)
				files.append(fpath)

		# Youtube etc are embedded as iframes.
		for ifr in ctnt_soup.find_all("iframe", src=True):
			ret['post_embeds'].append(ifr['src'])


		if len(files):
			self.log.info("Found %s images, %s attachments on post (%s total items).", len(shown_media), len(attachments), len(files))
		elif post_info['post_type'] == 'text_only':
			self.log.info("Text-only post %s!", item_id)

		else:
			self.log.warning("No images/attachments on post %s!", item_id)


		files = [filen for filen in files if filen]
		ret['dl_path'] = files
		ret['status']  = 'Succeeded'

		# pprint.pprint(ret)
		return ret


	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Underlying management
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def go(self, nameList=None, ctrlNamespace=None):

		if ctrlNamespace is None:
			raise ValueError("You need to specify a namespace!")
		is_another_active = self.getRunningStatus(self.pluginShortName)

		if is_another_active:
			self.log.error("Another instance of the %s scraper is running.", self.pluginShortName)
			self.log.error("Not starting")
			return
		try:

			self.cr = ChromeController.ChromeRemoteDebugInterface(
					binary             = "google-chrome",
					headless           = False,
					enable_gpu         = True,
					additional_options = ['--new-window']
				)


			self.updateRunningStatus(self.pluginShortName, True)
			startTime = datetime.datetime.now()
			self.updateLastRunStartTime(self.pluginShortName, startTime)

			# haveCookie, dummy_message = self.checkCookie()
			# if not haveCookie:
			# 	self.log.info("Do not have login cookie. Retreiving one now.")
			# 	cookieStatus, msg = self.getCookie()
			# 	self.log.info("Login attempt status = %s (%s).", cookieStatus, msg)
			# 	assert cookieStatus, "Login failed! Cannot continue!"

			# haveCookie, dummy_message = self.checkCookie()
			# if not haveCookie:
			# 	self.log.critical("Failed to download cookie! Exiting!")
			# 	return False

			# if not nameList:
			# 	nameList = self.getNameList()

			self.fetch_and_insert_new(self.cr)

			todo = self._getSiteToRetreive('pat')

			self.log.info("Have %s items to retreive", len(todo))

			# This /HAS/ to be single threaded, since it manipulates a single chromium instance.
			for todo_item in todo:
				fetch_ret = self.do_fetch_item(todo_item)
				_, artist_id, release_meta = todo_item
				artist_undecoded, _ = self._rid_to_artist_json(artist_id)
				artist_str          = self._rid_to_artist_name(artist_id)

				assert 'status'     in fetch_ret, "Status not in response!"

				if 'post_embeds' in fetch_ret:
					extends = fetch_ret['post_embeds']


				if fetch_ret['status'] == "Succeeded" or fetch_ret['status'] == "Exists":

					assert 'dl_path'    in fetch_ret
					assert 'page_desc'  in fetch_ret
					assert 'page_title' in fetch_ret
					assert 'post_time'  in fetch_ret
					assert 'post_tags'  in fetch_ret

					fetchtime = datetime.datetime.now()

					# Set the base row (if there's no files, we still set this, to allow text-only posts)
					self._updatePreviouslyRetreived(
							artist             = artist_str,
							state              = 'complete',
							release_meta       = release_meta,
							pageDesc           = fetch_ret['page_desc'],
							pageTitle          = fetch_ret['page_title'],
							addTime            = fetch_ret['post_time'],
							postTags           = fetch_ret['post_tags'],
							content_structured = fetch_ret,
							fetchTime          = fetchtime,
						)

					assert isinstance(fetch_ret['dl_path'], list)
					seq = 0
					for item in fetch_ret['dl_path']:
						self._updatePreviouslyRetreived(
								artist             = artist_str,
								state              = 'complete',
								release_meta       = release_meta,
								fqDlPath           = item,
								pageDesc           = fetch_ret['page_desc'],
								pageTitle          = fetch_ret['page_title'],
								seqNum             = seq,
								addTime            = fetch_ret['post_time'],
								postTags           = fetch_ret['post_tags'],
								content_structured = fetch_ret,
								fetchTime          = fetchtime,
							)
						seq += 1
				elif fetch_ret['status'] == "Ignore":
					self.log.info("Ignoring root URL, since it has child-pages.")
				else:
					self._updateUnableToRetrieve(artist_undecoded, release_meta)


			runTime = datetime.datetime.now()-startTime
			self.updateLastRunDuration(self.pluginShortName, runTime)

		finally:
			self.updateRunningStatus(self.pluginShortName, False)




	# ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Gallery Scraping
	# ---------------------------------------------------------------------------------------------------------------------------------------------------------

	def _getArtPage(self, *args, **kwargs):
		raise ValueError("Do not use this!")


def signal_handler(dummy_signal, dummy_frame):
	import flags
	if flags.namespace.run:
		flags.namespace.run = False
		self.log.info("Telling threads to stop")
	else:
		self.log.info("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt


def run_local():
	import multiprocessing
	import flags
	import signal

	manager = multiprocessing.Manager()
	flags.namespace = manager.Namespace()
	flags.namespace.run = True

	signal.signal(signal.SIGINT, signal_handler)

	print(sys.argv)
	ins = GetPatreonFeed()
	# ins.getCookie()
	print(ins)
	print("Instance: ", ins)

	# ins.go(ctrlNamespace=flags.namespace, update_namelist=True)
	ins.go(ctrlNamespace=flags.namespace)


if __name__ == '__main__':

	import sys
	import logSetup
	import logging
	logSetup.initLogging()
	# logSetup.initLogging(logLevel=logging.DEBUG)

	run_local()
