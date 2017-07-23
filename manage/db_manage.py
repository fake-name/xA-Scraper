

import flags
import os.path

import logSetup
from settings import settings

import signal
import time
import multiprocessing
import multiprocessing.managers
import sys
import sqlalchemy.exc
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
		# THis doesn't handle moving files yet, I should probably fix that.
		for item in from_p.files:
			if not os.path.split(item.fspath)[-1] in to_fn:
				item.item_id = to_p.id
			else:
				sess.delete(item)
		print("File mismatch!")
		print('from_fn', from_fn)
		print('to_fn', to_fn)

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

			from_p = release
			to_p   = sess.query(db.ArtItem).filter(db.ArtItem.artist_id == to_r.id) \
				.filter(db.ArtItem.release_meta == from_p.release_meta).one()

			move_delete_files(sess, from_p, to_p)
			move_delete_tags(sess, from_p, to_p)
			sess.delete(from_p)
			sess.commit()

	sess.delete(from_r)
	sess.commit()
	print("Removed OK")



def db_name_clean():
	print("db clean")
	with db.context_sess() as sess:
		artists = sess.query(db.ScrapeTargets).all()

		amap = {}
		for artist in artists:
			akey = (artist.site_name, artist.artist_name.lower())
			if akey in amap:
				print("Duplicate: ", akey)
				print(artist.site_name,     artist.artist_name)
				print(amap[akey].site_name, amap[akey].artist_name)

				# Frankly, if a site *isn't* case insensitive, I think they have a design flaw,
				# but it's something I consider.
				case_insensitive_sites = ['da', 'wy', 'ib', 'sf', 'hf']
				if artist.site_name in case_insensitive_sites:
					print("Deleting duplicate.")
					consolidate_artist(sess, artist, amap[akey])

			else:
				amap[akey] = artist
		sess.commit()
		# print(artists)




