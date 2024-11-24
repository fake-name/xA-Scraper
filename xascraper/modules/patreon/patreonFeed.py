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
				print("Not a 'new_post::' item: ", post_id)
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
				print("Did not have campaign: '%s'" % (db_name_items[camp_id], ))
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
	def do_fetch_item(self, item_row):
		pass


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
			# self.updateLastRunStartTime(self.pluginShortName, startTime)

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
				self.do_fetch_item(todo_item)

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
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
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
	logSetup.initLogging(logLevel=logging.DEBUG)

	run_local()
