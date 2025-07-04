

import flags
import tqdm
import json
import os.path

import logSetup
from settings import settings

import signal
import time
import sys
import re
import sqlalchemy.exc

from sqlalchemy.orm import joinedload
from sqlalchemy import func

import xascraper.database as db
import xascraper.status_monitor

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

def reset_run_state(plugin_name=None):

	resetter = xascraper.status_monitor.StatusResetter()

	if plugin_name:
		resetter.reset_specific_plugin_run_state(plugin_name)
	else:
		resetter.reset_all_plugins_run_state()


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
			print("Replaced ID on release '%s'" % (release.id, ))
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
		for artist in tqdm.tqdm(artists):
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
	have_other = sess.query(db.ArtItem).filter(db.ArtItem.artist_id == aid) \
			.filter(db.ArtItem.release_meta == row.release_meta)   \
			.scalar()
	if not have_other:
		print("No other match, simply changing AID")
		row.artist_id = aid
		print("committing")
		sess.commit()
		print("AID Directly replaced.")

	else:
		print("Have other target. Moving attachments instead.")
		print("Cross-links to ", have_other.artist_id, have_other.release_meta)
		merge_releases(sess, row, have_other)

def try_relink_artist(sess, row):
	print("Modifying", row.release_meta)

	wys = re.search(r'https://www\.weasyl\.com/~(.*?)/submissions/', row.release_meta)
	das = re.search(r'http://(.*?).deviantart.com/art/', row.release_meta)

	if wys:
		aname = wys.group(1)
		aid = _artist_name_to_rid(sess, 'wy', aname)
		if aid != row.artist_id:
			print("Switching AID from %s (%s) to %s (%s)" % (row.artist_id, (row.artist.site_name, row.artist.artist_name), aid, aname))
			replace_aid(sess, row, aid)
	if das:
		aname = das.group(1)
		aid = _artist_name_to_rid(sess, 'da', aname)
		if aid != row.artist_id:
			print("Switching AID from %s (%s) to %s (%s)" % (row.artist_id, (row.artist.site_name, row.artist.artist_name), aid, aname))
			replace_aid(sess, row, aid)

	if row.tags == [] and row.files == []:
		print("Could delete!")
		sess.delete(row)
		sess.commit()


def merge_release_set(sess, release_list):

	if "www.pixiv.net" in release_list[0].release_meta:
		return

	assert(all([release_list[0].release_meta == tmp.release_meta for tmp in release_list]))
	assert(all([release_list[0].artist_id == tmp.artist_id for tmp in release_list])), "Mismatched " \
		"artist IDs: '%s' -> '%s'" % ([(tmp.artist_id, tmp.artist.site_name, tmp.artist.artist_name, tmp.release_meta) for tmp in release_list], [release_list[0].artist_id == tmp.artist_id for tmp in release_list])
	print(release_list)

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


	try_relink_artist(sess, row)

	# if row.artist.site_name in url_expect_map:

	# 	if url_expect_map[row.artist.site_name] and url_expect_map[row.artist.site_name] in row.release_meta:
	# 		return
	# 	elif not url_expect_map[row.artist.site_name]:
	# 		return

	# print(sess, row.artist.site_name, row.release_meta)

def get_duplicated_attrs(session, cls, attr):
	return session.query(getattr(cls, attr)).group_by(getattr(cls, attr)) \
	       .having(func.count(getattr(cls, attr)) > 1).all()

def db_misrelink_clean():
	print('Misrelink cleaning')

	with db.context_sess() as sess:

		print("Geting duplicates")
		dupes = get_duplicated_attrs(sess, db.ArtItem, "release_meta")

		print("Duplicates:")
		for dupe_url, in dupes:
			releases = sess.query(db.ArtItem).options(joinedload('artist')) \
				.filter(db.ArtItem.release_meta == dupe_url).all()
			for release in releases:
				check_item(sess, release)

			releases_2 = sess.query(db.ArtItem).options(joinedload('artist')) \
				.filter(db.ArtItem.release_meta == dupe_url).all()
			if len(releases_2) > 1:
				merge_release_set(sess, releases)


def export_db_contents(to_path, site_name):
	print("Dumping contents for site %s to folder %s" % (site_name, to_path))

	ids = {}
	with db.context_sess() as sess:
		res = sess.query(db.ScrapeTargets)             \
			.filter(db.ScrapeTargets.site_name == site_name) \
			.all()
		for result in res:
			ids[result.id] = result.artist_name

	print("Found %s items!" % (len(ids), ))


	for uid, uname in tqdm.tqdm(ids.items(), desc="Artists"):
		with db.context_sess() as sess:
			posts = sess.query(db.ArtItem) \
				.filter(db.ArtItem.artist_id == uid) \
				.order_by(db.ArtItem.addtime) \
				.all()

			dat = []
			for post in tqdm.tqdm(posts, desc="Artist posts"):
				tmp = (
						uname,
						post.title,
						post.content,
						post.content_structured,
						list(ptag.tag for ptag in post.tags),
						list(
							(
								pfile.item_id,
								pfile.seqnum,
								pfile.file_meta,
								pfile.state,
								pfile.fspath,
								pfile.filename,
							)
							for pfile in post.files),
					)
				dat.append(tmp)

			outp = os.path.join(to_path, "%s-%s-%s-dump.json" % (site_name, uname, uid))
			with open(outp, "w") as fp:
				json.dump(dat, fp, indent=4)

def dump_item_meta():
	print("dump_item_meta")
	with db.context_sess() as sess:
		print("Counting")
		tot = sess.query(db.ArtFile).count()

		print("Have %s rows" % (tot))
		res_q = sess.query(db.ArtFile)

		print("Doing query")
		for row in tqdm.tqdm(res_q.yield_per(500), total=tot):

			tags               = [tag.tag for tag in row.item.tags]
			artist_name        = row.item.artist.artist_name
			site_name          = row.item.artist.site_name
			title              = row.item.title
			content            = row.item.content
			content_structured = row.item.content_structured
			filename           = row.fspath
			src_filename       = row.filename

			original_file_name = os.path.join(settings['dldCtntPath'], filename)
			write_to = os.path.join(settings['dldCtntPath'], filename+".json")

			if os.path.exists(original_file_name):
				with open(write_to, "w") as fp:
					fp.write(json.dumps(
							{
								"tags"               : tags,
								"artist_name"        : artist_name,
								"site_name"          : site_name,
								"title"              : title,
								"content"            : content,
								"content_structured" : content_structured,
								"filename"           : filename,
								"src_filename"       : src_filename,
							},
							indent = 4,
						))


def reset_missing():
	print("reset_missing")

	with db.context_sess() as sess:
		total_items = sess.query(db.ArtItem).count()

		for item in tqdm.tqdm(sess.query(db.ArtItem).yield_per(100), total=total_items):

			if item.artist.site_name in ['pat', 'twit', 'tum', 'yp', 'da']:
				continue
			if item.state == 'new':
				continue


			if not len(item.files):
				print("Item has no files: ", item.artist.site_name, item.state, item.title)
				item.state = 'new'
				sess.commit()



def fix_duplicates():
	# So I kind of fucked up my DB and wound up with some invalid indexes.
	# Anyways, I need a tool to clean them before I can reindex them successfully.

	# print("Fixing duplicates tags")

	seen_tags = {}
	with db.context_sess() as sess:
		total_items = sess.query(db.ArtTags).count()
		for rid, item_id, tag in tqdm.tqdm(sess.query(db.ArtTags.id, db.ArtTags.item_id, db.ArtTags.tag).yield_per(1000), total=total_items):
			seen_tags.setdefault((item_id, tag), []).append(rid)


	tag_dupes = {k : v for k, v in seen_tags.items() if len(v) > 1}

	print("Found %s duplicate tag entries" % (len(tag_dupes)))


	with db.context_sess() as sess:
		for key, dbids in tag_dupes.items():
			print("Deleting dupe for tag: ", (key, dbids))
			sess.query(db.ArtTags).filter(db.ArtTags.id==max(dbids)).delete()
			sess.commit()

	print("Fixing duplicates entries")

	seen_entries = {}
	with db.context_sess() as sess:
		total_items = sess.query(db.ArtItem).count()
		for rid, item_id, tag in tqdm.tqdm(sess.query(db.ArtItem.id, db.ArtItem.artist_id, db.ArtItem.release_meta).yield_per(1000), total=total_items):
			seen_entries.setdefault((item_id, tag), []).append(rid)


	entry_dupes = {k : v for k, v in seen_entries.items() if len(v) > 1}

	print("Found %s duplicate entries" % (len(entry_dupes)))


	with db.context_sess() as sess:
		for key, dbids in entry_dupes.items():
			print("Deleting dupe for entry: ", (key, dbids))
			sess.query(db.ArtItem).filter(db.ArtItem.id==max(dbids)).delete()
			sess.commit()


def delete_new_art_items():
	print("delete_new_art_items")
	with db.context_sess() as sess:
		patreon_aids = sess.query(db.ScrapeTargets.id) \
			.filter(db.ScrapeTargets.site_name == 'pat') \
			.all()
		patreon_aids = [item[0] for item in patreon_aids]

		print("Found %s patreon AIDs" % (len(patreon_aids), ))

		res = sess.query(db.ArtItem) \
			.filter(db.ArtItem.artist_id.in_(patreon_aids)) \
			.filter(db.ArtItem.state == 'new') \
			.count()
		print("Found %s new items" % (res, ))
		rids = sess.query(db.ArtItem.id) \
			.filter(db.ArtItem.artist_id.in_(patreon_aids)) \
			.filter(db.ArtItem.state == 'new') \
			.all()
		rids = [item[0] for item in rids]

		for rid in tqdm.tqdm(rids):
			try:
				sess.delete(sess.query(db.ArtItem).filter(db.ArtItem.id == rid).one())
				sess.commit()
			except sqlalchemy.exc.IntegrityError:
				sess.rollback()



# REINDEX (VERBOSE) TABLE art_item;
# REINDEX (VERBOSE) TABLE art_tag;

