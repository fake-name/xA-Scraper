"""Fix Pixiv URLs for new format

Revision ID: 46e1cef59e06
Revises: b7e0935213d5
Create Date: 2019-09-23 00:29:27.902652

"""

# revision identifiers, used by Alembic.
revision = '46e1cef59e06'
down_revision = 'b7e0935213d5'

import tqdm
import json
from alembic import op
import sqlalchemy as sa


def upgrade():
	conn = op.get_bind()
	print("Getting Pixiv DB Entries")
	px_releases = conn.execute("SELECT id, release_meta FROM art_item WHERE artist_id IN (SELECT id FROM scrape_targets WHERE site_name='px')")
	px_releases = list(px_releases)
	print("Fixing database entries")
	# This is dumb, but I should have used a tuple from the outset, because I need to be able to put
	# the release items in a set for various reasons.
	tot_changed = 0
	for rid, postid in tqdm.tqdm(px_releases):
		if 'uarea=response_out' in postid:
			print("Removing '%s'", postid)
			conn.execute("DELETE FROM art_tag WHERE item_id  = %s", (rid, ))
			conn.execute("DELETE FROM art_file WHERE item_id = %s", (rid, ))
			conn.execute("DELETE FROM art_item WHERE id = %s", (rid, ))

		elif "illust_id=" in postid:
			release_id = postid.split("illust_id=")[-1].split("&")[0]

			# if tot_changed % 1000 == 0:
			# 	conn.execute("COMMIT;")
			#
			try:
				postid = int(postid)

			except ValueError:
				print((rid, postid, release_id))
				raise

			value = {
				'type': 'illustration',
				'id'  : postid,
			}

			# post_params = json.loads(postid)
			# new_post = json.dumps((post_params['type'],  post_params['id']))
			changed = conn.execute("UPDATE art_item SET release_meta = %s WHERE id = %s", (json.dumps(value, sort_keys=True), rid))


		else:

			try:
				postid = int(postid)

			except ValueError:
				print((rid, postid, release_id))
				raise

			value = {
				'type': 'illustration',
				'id'  : postid,
			}

			# post_params = json.loads(postid)
			# new_post = json.dumps((post_params['type'],  post_params['id']))
			changed = conn.execute("UPDATE art_item SET release_meta = %s WHERE id = %s", (json.dumps(value, sort_keys=True), rid))


	print("Migrated!")
	if px_releases:
		conn.execute("COMMIT")

def downgrade():
	raise RuntimeError("Cannot downgrade!")
	pass
