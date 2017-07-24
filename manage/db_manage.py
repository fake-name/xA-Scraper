

import flags
import os.path

import logSetup
from settings import settings

import signal
import time
import multiprocessing
import multiprocessing.managers
import sys
import re
import sqlalchemy.exc
from sqlalchemy.orm import joinedload
import rewrite.database as db

def move_delete_files(sess, from_p, to_p):

	if not from_p.files:
		return

	from_fn = [os.path.split(tmp.fspath)[-1] for tmp in from_p.files]
	to_fn   = [os.path.split(tmp.fspath)[-1] for tmp in to_p.files]

	if all([tmp in to_fn for tmp in from_fn]):
		for item in from_p.files:
			sess.delete(item)

	else:
		# This doesn't handle moving files yet, I should probably fix that.

		if to_p.files:
			seqmax = max([f.seqnum for f in to_p.files]) + 1
		for item in from_p.files:
			if not os.path.split(item.fspath)[-1] in to_fn:
				item.item_id = to_p.id
				if to_p.files:
					item.seqnum = seqmax
					seqmax += 1
			else:
				sess.delete(item)

	sess.commit()

def move_delete_tags(sess, from_p, to_p):

	if not from_p.tags:
		return


	from_fn = [tmp.tag for tmp in from_p.tags]
	to_fn   = [tmp.tag for tmp in to_p.tags]

	if all([tmp in to_fn for tmp in from_fn]):
		print('remove')

		for item in from_p.tags:
			sess.delete(item)

	else:
		print("Tag mismatch!")
		print('from_fn', from_fn)
		print('to_fn', to_fn)
		for tag in from_p.tags:
			if tag.tag not in to_fn:
				print("Moving:", tag, tag.tag)
				tag.item_id = to_p.id
			else:
				print("Deleting:", tag, tag.tag)
				sess.delete(tag)
	sess.commit()

def merge_releases(sess, delete_r, to_p):
	print("Merging ", delete_r.artist_id, delete_r.release_meta)
	print("to      ", to_p.artist.site_name,       to_p.artist.artist_name,       to_p.release_meta)
	move_delete_files(sess, delete_r, to_p)
	move_delete_tags(sess, delete_r, to_p)
	sess.delete(delete_r)
	sess.commit()

def consolidate_artist(sess, from_r, to_r):

	releases = sess.query(db.ArtItem).filter(db.ArtItem.artist_id == from_r.id).all()

	for release in releases:
		try:
			release.artist_id = to_r.id
			sess.commit()
			print("Replaced ID")
		except sqlalchemy.exc.IntegrityError:
			sess.rollback()

			print("Duplicate: ", to_r.site_name, to_r.artist_name, release.id, release.release_meta)
			to_p   = sess.query(db.ArtItem).filter(db.ArtItem.artist_id == to_r.id) \
				.filter(db.ArtItem.release_meta == release.release_meta).one()
			merge_releases(sess, release, to_p)


	sess.delete(from_r)
	sess.commit()
	print("Removed OK")



def db_name_clean():
	print("db clean")
	with db.context_sess() as sess:
		artists = sess.query(db.ScrapeTargets).all()

		amap = {}
		for artist in artists:
			akey = (artist.site_name, artist.artist_name.lower().strip())
			if akey in amap:
				print("Duplicate: ", akey)
				print(artist.site_name,     artist.artist_name)
				print(amap[akey].site_name, amap[akey].artist_name)

				if artist.artist_name.strip() == artist.artist_name:
					good = artist
					bad = amap[akey]
				else:
					good = amap[akey]
					bad = artist

				print("Remove: %s -> '%s'" % (bad.site_name, bad.artist_name))
				print("Keep:   %s -> '%s'" % (good.site_name, good.artist_name))

				# Frankly, if a site *isn't* case insensitive, I think they have a design flaw,
				# but it's something I consider.
				case_insensitive_sites = ['da', 'wy', 'ib', 'sf', 'hf', 'fa', 'tum']
				if artist.site_name in case_insensitive_sites:
					print("Deleting duplicate.")
					consolidate_artist(sess, bad, good)

					sess.delete(bad)
					sess.commit()
			else:
				if artist.artist_name.strip() != artist.artist_name:
					print("Fixing whitespace: ", (artist.artist_name.strip(), artist.artist_name))
					artist.artist_name = artist.artist_name.strip()
					sess.commit()
				amap[akey] = artist
		sess.commit()
		# print(artists)


def _artist_name_to_rid(sess, site_name, aname):

	res = sess.query(db.ScrapeTargets.id)             \
		.filter(db.ScrapeTargets.site_name == site_name) \
		.filter(db.ScrapeTargets.artist_name.ilike(aname))              \
		.scalar()

	if res:
		return res
	else:
		return None

def replace_aid(sess, row, aid):
	print("replacing AID")
	try:

		row.artist_id = aid
		print("committing")
		sess.commit()
		print("AID Directly replaced.")

	except sqlalchemy.exc.IntegrityError:

		sess.rollback()
		print("Direct replacement failed. Moving attachments instead.")

		have = sess.query(db.ArtItem).filter(db.ArtItem.artist_id == aid) \
			.filter(db.ArtItem.release_meta == row.release_meta)   \
			.scalar()

		if have:

			print("Cross-links to ", have.artist_id, have.release_meta)
			merge_releases(sess, row, have)

		else:
			print("cannot find cross link! Wat?")

def try_relink_artist(sess, row):
	print("Artist ID is null! Wat?", row.release_meta)

	wys = re.search(r'https://www\.weasyl\.com/~(.*?)/submissions/', row.release_meta)
	das = re.search(r'http://(.*?).deviantart.com/art/', row.release_meta)
	sfs = re.search(r'https://www\.sofurry\.com/view/', row.release_meta)

	if wys:
		aname = wys.group(1)
		aid = _artist_name_to_rid(sess, 'wy', aname)
		replace_aid(sess, row, aid)
	if das:
		aname = das.group(1)
		aid = _artist_name_to_rid(sess, 'da', aname)
		replace_aid(sess, row, aid)
	if sfs:
		# No artist name embedded in URL
		return


def check_item(sess, row):
	url_expect_map = {
		 "da"    : '.deviantart.com',
		 "fa"    : 'www.furaffinity.net',
		 "hf"    : 'www.hentai-foundry.com',
		 "wy"    : 'www.weasyl.com',
		 "ib"    : 'inkbunny.net',
		 "px"    : 'www.pixiv.net',
		 "sf"    : 'www.sofurry.com',
		"tum"    : '.tumblr.com',
		"pat"    : None,
	}

	if not row.artist_id:
		try_relink_artist(sess, row)
		return

	if row.artist.site_name in url_expect_map:
		if url_expect_map[row.artist.site_name] and url_expect_map[row.artist.site_name] in row.release_meta:
			return
		elif not url_expect_map[row.artist.site_name]:
			return

	print(sess, row.artist.site_name, row.release_meta)

def db_misrelink_clean():
	print('Misrelink cleaning')

	with db.context_sess() as sess:
		print("Querying...")
		releases = sess.query(db.ArtItem).options(joinedload('artist')).all()
		print("Query complete. Parsing.")
		for release in releases:
			check_item(sess, release)








