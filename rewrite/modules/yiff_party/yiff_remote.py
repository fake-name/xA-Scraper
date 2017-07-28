
import os
import os.path
import traceback
import re
import logging
import datetime
import urllib.request
import urllib.parse
import time
import json
import uuid
import pprint

import bs4
import dateparser

import rewrite.modules.scraper_base
import rewrite.modules.rpc_base

import flags

from settings import settings

class RpcTimeoutError(RuntimeError):
	pass
class RpcExceptionError(RuntimeError):
	pass


class RemoteExecClass(object):
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------
	# Runtime management
	# # ---------------------------------------------------------------------------------------------------------------------------------------------------------

	url_base = 'https://yiff.party/'

	def __init__(self, wg=None):
		self.logname = "Main.RemoteExec.Tester"
		self.out_buffer = []

		self.wg = wg

		self.__install_logproxy()

		self.log.info("RemoteExecClass Instantiated")

	def __install_logproxy(self):
		class LogProxy():
			def __init__(self, parent_logger, log_prefix):
				self.parent_logger = parent_logger
				self.log_prefix    = log_prefix
			def debug(self, msg, *args):
				self.parent_logger._debug   (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def info(self, msg, *args):
				self.parent_logger._info    (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def error(self, msg, *args):
				self.parent_logger._error   (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def critical(self, msg, *args):
				self.parent_logger._critical(" [{}] -> ".format(self.log_prefix) + msg, *args)
			def warning(self, msg, *args):
				self.parent_logger._warning (" [{}] -> ".format(self.log_prefix) + msg, *args)
			def warn(self, msg, *args):
				self.parent_logger._warning (" [{}] -> ".format(self.log_prefix) + msg, *args)

		self.wg.log = LogProxy(self, "WebGet")
		self.log    = LogProxy(self, "MainRPCAgent")


	def _debug(self, msg, *args):
		tmp = self.logname + " [DEBUG] ->" + msg % args
		self.out_buffer.append(tmp)
	def _info(self, msg, *args):
		tmp = self.logname + " [INFO] ->" + msg % args
		self.out_buffer.append(tmp)
	def _error(self, msg, *args):
		tmp = self.logname + " [ERROR] ->" + msg % args
		self.out_buffer.append(tmp)
	def _critical(self, msg, *args):
		tmp = self.logname + " [CRITICAL] ->" + msg % args
		self.out_buffer.append(tmp)
	def _warning(self, msg, *args):
		tmp = self.logname + " [WARNING] ->" + msg % args
		self.out_buffer.append(tmp)


	def go(self, *args, **kwargs):
		try:
			ret = self._go(*args, **kwargs)
			return (self.out_buffer, ret)
		except Exception as e:
			import sys
			log_txt = '\n	'.join(self.out_buffer)
			exc_message = '{}\nLog report:\n	{}'.format(str(e), log_txt)
			rebuilt = type(e)(exc_message).with_traceback(sys.exc_info()[2])
			rebuilt.log_data = self.out_buffer
			raise rebuilt

	# # ------------------------------------------------------------------------
	# User-facing type things
	# # ------------------------------------------------------------------------

	def yp_walk_to_entry(self):
		gateway = 'https://8ch.net/fur/res/22069.html'
		step1 = self.wg.getpage(gateway)
		self.log.debug("Step 1")
		extraHeaders = {
					"Referer"       : gateway,
		}

		step2 = self.wg.getpage('https://yiff.party/zauth', addlHeaders=extraHeaders)
		self.log.debug("Step 2")

		if 'What is the name of the character pictured above?' in step2:
			self.log.info("Need to step through confirmation page.")
			params = {
				'act'       : 'anon_auth',
				'challenge' : 'anon_auth_1',
				'answer'    : 'nate',
			}
			step3 = self.wg.getpage('https://yiff.party/intermission', postData=params)
			self.log.debug("Step 3")
		else:
			step3 = step2

		if 'You have no favourite creators!' in step3:
			self.log.info("Reached home page!")
			return True
		else:
			self.log.error("Failed to reach home page!")
			self.log.error("Step 1")
			for line in step1.split("\n"):
				self.log.error("	%s", line)
			self.log.error("Step 2")
			for line in step2.split("\n"):
				self.log.error("	%s", line)
			self.log.error("Step 3")
			for line in step3.split("\n"):
				self.log.error("	%s", line)
			return False

	def yp_get_names(self):
		self.log.info("Getting available artist names!")
		ok = self.yp_walk_to_entry()
		if ok:
			return self.wg.getpage('https://yiff.party/creators2.json', addlHeaders={"Referer" : 'https://yiff.party/'})
		else:
			return None

	def get_meta_from_release_soup(self, release_soup):
		retv = {}

		name = release_soup.find('span', class_='yp-info-name')
		if name:
			retv['artist_name'] = name.get_text(strip=True)

		return retv

	def get_posts_from_page(self, soup):
		posts = []
		postdivs = soup.find_all("div", class_='yp-post')
		for postdiv in postdivs:
			post = {}
			post['id'] = postdiv['id']

			post['time']  = postdiv.find(True, class_='post-time' ).get_text(strip=True)
			post['title'] = list(postdiv.find("span", class_='card-title').stripped_strings)[0]
			post['body']  = postdiv.find("div",   class_='post-body' ).get_text(strip=True)

			attachment_div = postdiv.find("div", class_='card-attachments')
			attachments = []
			if attachment_div:
				for link in attachment_div.find_all("a"):
					url = urllib.parse.urljoin(self.url_base, link['href'])
					content = link.get_text(strip=True)
					attachments.append({'url' : url,  'fname' : content})

			# Somehow, some of the files don't show up
			# as attachments. Dunno why.
			action_div = postdiv.find("div", class_='card-action')
			if action_div:
				for link in action_div.find_all("a"):
					url = urllib.parse.urljoin(self.url_base, link['href'])
					content = link.get_text(strip=True)
					attachments.append({'url' : url,  'fname' : content})

			post['attachments'] = attachments

			comments = []
			for comment_div in postdiv.find_all('div', class_='yp-post-comment'):
				comment = {}
				comment['content']  = comment_div.find(True, class_='yp-post-comment-body').get_text(strip=True)
				comment['time_utc'] = comment_div.find(True, class_='yp-post-comment-time')['data-utc']
				comment['author']   = list(comment_div.find(True, class_='yp-post-comment-head').stripped_strings)[0]

				comments.append(comment)
			post['comments'] = comments
			posts.append(post)

		return posts

	def get_files_from_page(self, soup):
		files = []
		file_divs = soup.find_all('div', class_='yp-shared-card')
		for file_div in file_divs:

			file = {}
			file['title'] = list(file_div.find(True, class_='card-title').stripped_strings)[0]
			file['post_ts'] = file_div.find(True, class_='post-time-unix').get_text(strip=True)

			content = file_div.find('div', class_='card-action')

			file['attachments'] = [
				(tmp.get_text(strip=True), urllib.parse.urljoin(self.url_base, tmp['href'])) for tmp in content.find_all('a')
			]
			files.append(file)

		return files


	def get_releases_for_aid(self, aid):
		soup = self.wg.getSoup('https://yiff.party/{}'.format(aid), addlHeaders={"Referer" : 'https://yiff.party/'})

		# Clear out the material design icons.
		for baddiv in soup.find_all("i", class_='material-icons'):
			baddiv.decompose()

		meta = self.get_meta_from_release_soup(soup)

		posts = self.get_posts_from_page(soup)
		files = self.get_files_from_page(soup)

		return {
			'meta'   : meta,
			'posts' : posts,
			'files' : files,
		}

	def fetch_post_content(self, aid, post):

		for attachment in post['attachments']:
			self.log.info("Fetching post file: %s -> %s", aid, attachment['url'])
			filectnt, fname         = self.wg.getFileAndName(attachment['url'], addlHeaders={"Referer" : 'https://yiff.party/{}'.format(aid)})
			self.log.info("Filename from request: %s", fname)
			attachment['header_fn'] = fname
			attachment['fdata']     = filectnt

	def fetch_file_content(self, aid, post):

		for attachment in post['attachments']:
			self.log.info("Fetching attachment file: %s -> %s", aid, attachment['url'])
			filectnt, fname         = self.wg.getFileAndName(attachment['url'], addlHeaders={"Referer" : 'https://yiff.party/{}'.format(aid)})
			self.log.info("Filename from request: %s", fname)
			attachment['header_fn'] = fname
			attachment['fdata']     = filectnt

	def fetch_files(self, aid, releases, have_posts, file_limit):
		self.log.info("Have posts: %s", have_posts)
		fetched = 0

		releases['posts'].reverse()
		releases['files'].reverse()

		skipped = 0

		for post in releases['posts']:
			key = ['post', post['id']]
			if key in have_posts:
				self.log.info("Have post %s, nothing to do", key)
				post['skipped'] = True
				skipped += 1
			elif fetched > file_limit:
				self.log.info("Skipping %s due to fetch limit %s.", key, file_limit)
				post['skipped'] = True
				skipped += 1
			else:
				self.log.info("Item %s not present in already-fetched items.", key)
				post['files'] = self.fetch_post_content(aid, post)
				fetched += 1


		for file in releases['files']:
			key = ['post', file['title']]
			if key in have_posts:
				self.log.info("Have file %s, nothing to do", key)
				file['skipped'] = True
				skipped += 1
			elif fetched > file_limit:
				self.log.info("Skipping %s due to fetch limit %s.", key, file_limit)
				file['skipped'] = True
				skipped += 1
			else:
				self.log.info("File %s not present in already-fetched items.", key)
				file['files'] = self.fetch_file_content(aid, file)
				fetched += 1

		self.log.info("Skipped %s files", skipped)

		return releases


	def yp_get_content_for_artist(self, aid, have_posts, file_limit=25):
		self.log.info("Getting content for artist: %s", aid)
		ok = self.yp_walk_to_entry()
		if not ok:
			return "Error! Failed to access entry!"

		releases = self.get_releases_for_aid(aid)
		releases = self.fetch_files(aid, releases, have_posts, file_limit)
		# else:
		self.log.info("Content retreival finished.")
		return releases

	def _go(self, mode, **kwargs):
		self.log.info("_go() called with mode: '%s'", mode)
		self.log.info("_go() kwargs: '%s'", kwargs)

		if mode == 'yp_get_names':
			return self.yp_get_names()
		elif mode == "yp_get_content_for_artist":
			return self.yp_get_content_for_artist(**kwargs)
		else:
			self.log.error("Unknown mode: '%s'", mode)
			return "Unknown mode: '%s' -> Kwargs: '%s'" % (mode, kwargs)


