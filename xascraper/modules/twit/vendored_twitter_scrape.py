import re
import time
import traceback
import logging
import datetime
import urllib.parse
import urllib.request
import json
import dateparser
import WebRequest
from requests_html import HTML
from lxml.etree import ParserError
from xascraper.modules import exceptions


class TwitterFetcher(object):
	def __init__(self, wg):
		self.log = logging.getLogger("Main.TwitterInterface")

		self.wg = wg
		self.current_url = None


	def getToken(self):
		self.log.info("Getting Entrance Cookie")
		# We need to let the twitter JS set the csrf cookie, so we can use it later
		self.wg.stepThroughJsWaf(url='https://mobile.twitter.com/Twitter', titleContains="@Twitter")

		csrf_cook = [cook for cook in self.wg.cj if cook.domain.endswith(".twitter.com") and cook.name == 'ct0']
		if not csrf_cook:
			raise exceptions.NotLoggedInException("Cannot get csrf cookie!")
		self.log.info("Done")




	# Ugh, I need to clean up the function names in WebGet at some point.
	def stateful_get(self, url, headers=None, params=None):
		return self.__stateful_get("getpage", url, headers, params)

	def stateful_get_soup(self, url, headers=None, params=None):
		return self.__stateful_get("getSoup", url, headers, params)

	def stateful_get_json(self, url, headers=None, params=None):
		return self.__stateful_get("getJson", url, headers, params)

	def __stateful_get(self, call_name, url, headers, params):

		if headers is None:
			headers = {}

		if params is not None:
			assert isinstance(params, dict), "Parameters, if passed, must be a dict. Passed %s" % (type(params), )
			scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)[:5]

			qparsed = urllib.parse.parse_qs(query)

			# Update the URL from the passed parameters
			for key, value in params.items():
				qparsed[key] = [value]

			query = urllib.parse.urlencode(qparsed, doseq=True)

			url = urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))

		if self.current_url:
			headers["Referer"] = self.current_url
		self.current_url = url

		func = getattr(self.wg, call_name)
		page = func(url, addlHeaders=headers)
		return page


	def __extract_tweet(self, tweet):

		# 10~11 html elements have `.stream-item` class and also their `data-item-type` is `tweet`
		# but their content doesn't look like a tweet's content
		try:
			text = tweet.find('.tweet-text')[0].full_text
		except IndexError:  # issue #50
			return None

		tweet_id = tweet.attrs['data-item-id']

		tweet_post_time = float(tweet.find('._timestamp')[0].attrs['data-time-ms']) / 1000.0

		interactions = [
			x.text
			for x in tweet.find('.ProfileTweet-actionCount')
		]

		comma = ","
		dot = "."

		replies = int(
			interactions[0].split(' ')[0].replace(comma, '').replace(dot, '')
			or interactions[3]
		)

		retweets = int(
			interactions[1].split(' ')[0].replace(comma, '').replace(dot, '')
			or interactions[4]
			or interactions[5]
		)

		likes = int(
			interactions[2].split(' ')[0].replace(comma, '').replace(dot, '')
			or interactions[6]
			or interactions[7]
		)

		hashtags = [
			hashtag_node.full_text
			for hashtag_node in tweet.find('.twitter-hashtag')
		]
		urls = [
			url_node.attrs['data-expanded-url']
			for url_node in tweet.find('a.twitter-timeline-link:not(.u-hidden)')
		]
		photos = [
			photo_node.attrs['data-image-url']
			for photo_node in tweet.find('.AdaptiveMedia-photoContainer')
		]


		is_retweet = bool(tweet.find('.js-stream-tweet')[0].attrs.get('data-retweet-id', None))
		tweet_auth = tweet.find('.js-stream-tweet')[0].attrs.get('data-screen-name')

		videos = []
		video_nodes = tweet.find(".PlayableMedia-player")
		for node in video_nodes:
			styles = node.attrs['style'].split()
			for style in styles:
				if style.startswith('background'):
					tmp = style.split('/')[-1]
					try:
						video_id = tmp[:tmp.index('.jpg')]
					except ValueError:
						try:
							video_id = tmp[:tmp.index('.png')]
						except ValueError:
							video_id = tmp[:tmp.index('?')]
					videos.append({'id': video_id})

		return {
					'tweetId'      : tweet_id,
					'isRetweet'    : is_retweet,
					'tweet_author' : tweet_auth,
					'time'         : tweet_post_time,
					'text'         : text,
					'replies'      : replies,
					'retweets'     : retweets,
					'likes'        : likes,
					'entries': {
						'hashtags' : hashtags,
						'urls'     : urls,
						'photos'   : photos,
						'videos'   : videos
					}
				}


	def get_joined_date(self, user):
		ctnt = self.stateful_get_soup("https://mobile.twitter.com/{user}".format(user=user))

		scripts = ctnt.find_all("script", type="text/javascript", src=True)
		script_url = None
		for script_tag in scripts:
			if "/main." in str(script_tag.get("src")):
				script_url = script_tag.get("src")

		assert script_url

		script = self.stateful_get(script_url).decode("utf-8")

		# print(script)

		export_search_re = re.compile(r'exports={queryId:"(\w+?)",operationName:"UserByScreenName",operationType:"query"}')
		authorization_re = re.compile(r'=\"(AAAAAAAA[a-zA-Z0-9\%]*?)\"')
		export_res = export_search_re.search(script)
		auth_res   = authorization_re.search(script)

		csrf_cook   = [cook for cook in self.wg.cj if cook.domain.endswith(".twitter.com") and cook.name == 'ct0'][0]
		guest_cook  = [cook for cook in self.wg.cj if cook.domain.endswith(".twitter.com") and cook.name == 'guest_id'][0]
		guest_token = guest_cook.value.split("A")[-1]

		print("Export RE result: ", export_res, export_res.groups())
		print("Auth RE result: ", auth_res, auth_res.groups())

		# Pulled out of twitter's main.js
		# This is probably super brittle, and will break
		query_id = export_res.group(1)
		params = [
			('variables', '{"screen_name":"%s","withHighlightedLabel":false}' % user)
		]

		api_url = "https://api.twitter.com/graphql/%s/UserByScreenName?%s" % (query_id, urllib.parse.urlencode(params))


		request_1 = urllib.request.Request(api_url, method="OPTIONS")

		for key, value in self.wg.browserHeaders:
			request_1.add_header(key, value)

		request_1.add_header('accept', '*/*')
		request_1.add_header('access-control-request-method', 'GET')
		request_1.add_header('access-control-request-headers', 'authorization,content-type,x-csrf-token,x-guest-token,x-twitter-active-user,x-twitter-client-language')
		request_1.add_header('cache-control', 'no-cache')

		request_1.add_header('referer', 'https://mobile.twitter.com/{}'.format(user))
		request_1.add_header('origin', 'https://mobile.twitter.com')
		request_1.add_header('pragma', 'no-cache')
		request_1.add_header('sec-fetch-mode', 'cors')
		request_1.add_header('sec-fetch-site', 'same-site')



		try:
			resp_1 = self.wg.opener.open(request_1)
			print("Options request OK")
		except Exception as e:
			print("Exception1!")
			print("E: ", e)
			import pdb
			pdb.set_trace()


		request_2 = urllib.request.Request(api_url)

		for key, value in self.wg.browserHeaders:
			request_2.add_header(key, value)

		request_2.add_header('accept', '*/*')
		request_2.add_header('referer', 'https://mobile.twitter.com/{}'.format(user))
		request_2.add_header('origin', 'https://mobile.twitter.com')
		request_2.add_header('pragma', 'no-cache')
		request_2.add_header('sec-fetch-mode', 'cors')
		request_2.add_header('content-type', 'application/json')
		request_2.add_header('x-twitter-active-user', 'yes')
		request_2.add_header('x-twitter-client-language', 'en')
		request_2.add_header('x-csrf-token', csrf_cook.value)
		request_2.add_header('x-guest-token', guest_token)
		request_2.add_header('authorization', 'Bearer %s' % auth_res.group(1))


		try:
			resp_2 = self.wg.opener.open(request_2)
		except Exception as e:
			print("Exception2!")
			print("E: ", e)
			traceback.print_exc()
			import pdb
			pdb.set_trace()

		# print(ctnt)


		# yield from self.gen_tweets(url, twit_headers, username)

		return

		ctnt = self.stateful_get("https://mobile.twitter.com/{user}".format(user=user))
		html = HTML(html=ctnt)
		joined_items = html.find(".ProfileHeaderCard-joinDateText")
		if not joined_items:
			raise exceptions.AccountDisabledException("Could not retreive artist joined date. "
				"This usually means the account has been disabled!")

		assert len(joined_items) == 1, "Too many joined items?"
		joined = joined_items[0]

		posttime = dateparser.parse(joined.attrs['title'])

		self.log.info("User %s joined twitter at %s", user, posttime)

		return posttime

	def gen_tweets(self, url, twit_headers, username):

		response_json = self.stateful_get_json(url, headers=twit_headers)

		total_items = 0
		while True:

			if not response_json['items_html'].strip():
				break

			try:
				html = HTML(html=response_json['items_html'], url='bunk', default_encoding='utf-8')
			except KeyError:
				raise ValueError(f'Oops! Either "{username}" does not exist or is private.')
			except ParserError:
				traceback.print_exc()
				print("Page: ", response_json)
				break

			tweets = []
			for tweet in html.find('.stream-item'):
				extr_tweet = self.__extract_tweet(tweet)
				if extr_tweet:
					tweets.append(extr_tweet)


			stream_item = html.find('.stream-item')
			if not stream_item:
				self.log.warning("No items for query! Did the user not tweet for the relevant interval?")
				break

			last_tweet = stream_item[-1].attrs['data-item-id']


			on_page = 0
			for tweet in tweets:
				if tweet:
					on_page += 1
					total_items += 1
					tweet['text'] = re.sub(r'\Shttp', ' http', tweet['text'], 1)
					tweet['text'] = re.sub(r'\Spic\.twitter', ' pic.twitter', tweet['text'], 1)
					yield tweet

			if 'has_more_items' in response_json and not response_json['has_more_items']:
				self.log.info("Out of items. Found %s tweets for last username", on_page)
				break

			self.log.info("Sleeping to do rate limiting. Found %s tweets for last username", on_page)
			# print("Response.json", response_json)
			time.sleep(5)

			if "min_position" in response_json:
				response_json = self.stateful_get_json(url, params={'max_position': response_json["min_position"]}, headers=twit_headers)
			else:
				response_json = self.stateful_get_json(url, params={'max_position': last_tweet}, headers=twit_headers)

		self.log.info("Total items found: %s", total_items)

	def gen_tweets_for_date_span(self, username, start_date, end_date):
		from_date = start_date.isoformat()[:10]
		to_date   = end_date.isoformat()[:10]

		url = "https://twitter.com/search?q=from%3A{user}%20since%3A{from_date}%20until%3A{to_date}&src=typd".format(
			user=username, from_date=from_date, to_date=to_date)

		url = "https://twitter.com/i/search/timeline?vertical=default&q=from%3A{user}%20since%3A{from_date}%20until%3A{to_date}&src=typd&include_available_features=1&include_entities=1&reset_error_state=false".format(
			user=username, from_date=from_date, to_date=to_date)

		twit_headers = {
			'Accept': 'application/json, text/javascript, */*; q=0.01',
			'Referer': 'https://twitter.com/',
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
			'X-Twitter-Active-User': 'yes',
			'X-Requested-With': 'XMLHttpRequest',
			'Accept-Language': 'en-US'
		}

		# print("Url:", url)
		yield from self.gen_tweets(url, twit_headers, username)

	def get_recent_tweets(self, username):
		"""Gets tweets for a given user, via the Twitter frontend API."""

		twit_headers = {
			'Accept': 'application/json, text/javascript, */*; q=0.01',
			'Referer': 'https://twitter.com/{username}'.format(username=username),
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
			'X-Twitter-Active-User': 'yes',
			'X-Requested-With': 'XMLHttpRequest',
			'Accept-Language': 'en-US'
		}

		url = 'https://twitter.com/i/profiles/show/{username}/timeline/tweets?include_available_features=1&include_entities=1&include_new_items_bar=true'.format(username=username)

		yield from self.gen_tweets(url, twit_headers, username)

	def get_all_tweets(self, username, minimum_date=None):
		"""
		Gets tweets for a given user, via the Twitter frontend API.

		Note that due to the way the overlapping time intervals are generated, this WILL return duplicates
		of the same tweet. For my use, I don't care. If this is a problem for your use case, you'll need
		to handle it yourself.
		"""

		twit_headers = {
			'Accept': 'application/json, text/javascript, */*; q=0.01',
			'Referer': 'https://twitter.com/{username}'.format(username=username),
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
			'X-Twitter-Active-User': 'yes',
			'X-Requested-With': 'XMLHttpRequest',
			'Accept-Language': 'en-US'
		}

		url = 'https://twitter.com/i/profiles/show/{username}/timeline/tweets?include_available_features=1&include_entities=1&include_new_items_bar=true'.format(username=username)

		interval_start = self.get_joined_date(username)

		if minimum_date and minimum_date > interval_start:
			self.log.info("Limiting last-scraped interval start to %s (joined date %s)", minimum_date, interval_start)
			interval_start = minimum_date

		chunk_interval = datetime.timedelta(days=7)
		overlap = datetime.timedelta(days=2)



		while interval_start < datetime.datetime.now():

			tgt_start = interval_start - overlap
			tgt_end   = interval_start + chunk_interval


			for item in self.gen_tweets_for_date_span(username, tgt_start, tgt_end):
				yield item

			interval_start = tgt_end


		# yield from self.gen_tweets(url, twit_headers, username)
