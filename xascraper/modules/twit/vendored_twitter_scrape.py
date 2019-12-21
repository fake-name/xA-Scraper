import re
import time
import traceback
import logging
import datetime
import urllib.parse
import dateparser
from requests_html import HTML
from lxml.etree import ParserError


class TwitterFetcher(object):
	def __init__(self, wg):
		self.log = logging.getLogger("Main.TwitterInterface")

		self.wg = wg
		self.current_url = None

	# Ugh, I need to clean up the function names in WebGet at some point.
	def stateful_get(self, url, headers=None, params=None):
		return self.__stateful_get("getpage", url, headers, params)

	def stateful_get_soup(self, url, headers=None, params=None):
		return self.__stateful_get("getsoup", url, headers, params)

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

		tweet_post_time = int(tweet.find('._timestamp')[0].attrs['data-time-ms']) / 1000.0

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
					video_id = tmp[:tmp.index('.jpg')]
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

		ctnt = self.stateful_get("https://twitter.com/{user}".format(user=user))
		html = HTML(html=ctnt)
		joined_items = html.find(".ProfileHeaderCard-joinDateText")
		assert joined_items, "No joined items?"
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

			last_tweet = html.find('.stream-item')[-1].attrs['data-item-id']


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

	def get_all_tweets(self, username):
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

		joined_date = self.get_joined_date(username)

		chunk_interval = datetime.timedelta(days=7)
		overlap = datetime.timedelta(days=2)

		interval_end = datetime.datetime.now()

		while interval_end > joined_date:
			tgt_start = interval_end - chunk_interval
			tgt_end   = interval_end + overlap

			print("Should fetch for ", tgt_start, tgt_end)

			for item in self.gen_tweets_for_date_span(username, tgt_start, tgt_end):
				yield item

			interval_end = tgt_start


		# yield from self.gen_tweets(url, twit_headers, username)
