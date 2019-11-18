import re
import time
import traceback
import logging
from requests_html import HTMLSession, HTML
from datetime import datetime
from urllib.parse import quote
from lxml.etree import ParserError
import mechanicalsoup


class TwitterFetcher(object):
	def __init__(self):
		self.log = logging.getLogger("Main.TwitterInterface")
		self.session = HTMLSession()
		self.browser = mechanicalsoup.StatefulBrowser()
		self.browser.addheaders = [('User-agent', 'Firefox')]

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

	def gen_tweets(self, url, twit_headers, query):
		r = self.session.get(url, headers=twit_headers)

		while True:
			try:
				html = HTML(html=r.json()['items_html'], url='bunk', default_encoding='utf-8')
			except KeyError:
				raise ValueError(f'Oops! Either "{query}" does not exist or is private.')
			except ParserError:
				traceback.print_exc()
				print("Page: ", r, r.json())
				break

			tweets = []
			for tweet in html.find('.stream-item'):
				extr_tweet = self.__extract_tweet(tweet)
				if extr_tweet:
					tweets.append(extr_tweet)

			last_tweet = html.find('.stream-item')[-1].attrs['data-item-id']

			for tweet in tweets:
				if tweet:
					tweet['text'] = re.sub(r'\Shttp', ' http', tweet['text'], 1)
					tweet['text'] = re.sub(r'\Spic\.twitter', ' pic.twitter', tweet['text'], 1)
					yield tweet

			self.log.info("Sleeping to do rate limiting")
			time.sleep(5)
			r = self.session.get(url, params={'max_position': last_tweet}, headers=twit_headers)

	def get_tweets(self, query):
		"""Gets tweets for a given user, via the Twitter frontend API."""

		twit_headers = {
			'Accept': 'application/json, text/javascript, */*; q=0.01',
			'Referer': 'https://twitter.com/{query}'.format(query=query),
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8',
			'X-Twitter-Active-User': 'yes',
			'X-Requested-With': 'XMLHttpRequest',
			'Accept-Language': 'en-US'
		}

		url = 'https://twitter.com/i/profiles/show/{query}/timeline/tweets?include_available_features=1&include_entities=1&include_new_items_bar=true'.format(query=query)

		yield from self.gen_tweets(url, twit_headers, query)
