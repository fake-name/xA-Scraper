"""empty message

Revision ID: 6937420ccb1b
Revises: None
Create Date: 2017-07-11 05:11:03.555910

"""

# revision identifiers, used by Alembic.
revision = '6937420ccb1b'
down_revision = None

from alembic import op
import sqlalchemy as sa
import citext
import datetime
import settings
from sqlalchemy.dialects import postgresql
import os.path

def migrate_data():

    conn = op.get_bind()
    res = conn.execute('''
        SELECT
             sitename,
             artistname,
             uploadeh,
             last_fetched
        FROM siteartistnames;
        ''')
    data = res.fetchall()


    moar = conn.execute("""
        SELECT
            sitename,
            artistname
        FROM
            retrieved_pages
        GROUP BY
            sitename,
            artistname
        """)
    res2 = moar.fetchall()



    have = [
        (sitename, artistname)
        for
            sitename,
            artistname,
            uploadeh,
            last_fetched
        in
            data
        ]

    sources = [
        {
            'site_name': sitename,
            'artist_name':artistname,
            'uploadeh': bool(uploadeh),
            'last_fetched': datetime.datetime.utcfromtimestamp(last_fetched)
        }
        for
            sitename,
            artistname,
            uploadeh,
            last_fetched
        in
            data
        ]

    missing = 0
    for sitename, artistname in res2:
        if not (sitename, artistname) in have:
            missing += 1
            sources.append({
                    'site_name': sitename,
                    'artist_name':artistname,
                    'uploadeh': False,
                    'last_fetched': datetime.datetime.min
                })
    print("Found %s missing targets from the artist list. %s total items" % (missing, len(sources)))

    op.bulk_insert(scrape_targets_tbl, sources)

    res = conn.execute('''
        SELECT
             id,
             site_name,
             artist_name
        FROM scrape_targets;
        ''')
    raw_uid_map = res.fetchall()

    user_map = {(site, user) : rid for rid, site, user in raw_uid_map}
    user_reverse_map = {rid : (site, user) for rid, site, user in raw_uid_map}


    ##########################################################################################
    ##########################################################################################

    # xa_downloader=# \d retrieved_pages
    #                               Table "public.retrieved_pages"
    #      Column      |  Type   |                          Modifiers
    # -----------------+---------+--------------------------------------------------------------
    #  id              | integer | not null default nextval('retrieved_pages_id_seq'::regclass)
    #  sitename        | text    | not null
    #  artistname      | text    | not null
    #  pageurl         | text    | not null
    #  retreivaltime   | real    | not null
    #  downloadpath    | text    |
    #  itempagecontent | text    |
    #  itempagetitle   | text    |
    #  seqnum          | integer |
    # Indexes:
    #     "retrieved_pages_pkey" PRIMARY KEY, btree (id)
    #     "retrieved_pages_sitename_artistname_pageurl_seqnum_key" UNIQUE CONSTRAINT, btree (sitename, artistname, pageurl, seqnum)
    #     "retrieved_pages_artistname_index" btree (artistname)
    #     "retrieved_pages_pageurl_index" btree (pageurl)
    #     "retrieved_pages_site_src_time_index" btree (sitename, retreivaltime)
    #     "retrieved_pages_time_index" btree (retreivaltime)

    print("Fetching all items")
    res = conn.execute('''
        SELECT
            sitename,
            artistname,
            pageurl,
            retreivaltime,
            downloadpath,
            itempagecontent,
            itempagetitle,
            seqnum
        FROM retrieved_pages;
        ''')
    data = res.fetchall()
    print("Found %s data rows. Processing" % len(data))

    grouped = {}
    for sitename, artistname, pageurl, retreivaltime, downloadpath, itempagecontent, itempagetitle, seqnum in data:
        # So... DA does deduplication on content (I think?), so reposts often get multiple references
        # to the same underlying URL.
        itemkey = (sitename, artistname, pageurl)
        grouped.setdefault(itemkey, [])
        grouped[itemkey].append(
                {
                    'sitename'        : sitename,
                    'artistname'      : artistname,
                    'pageurl'         : pageurl,
                    'retreivaltime'   : retreivaltime,
                    'downloadpath'    : downloadpath,
                    'itempagecontent' : itempagecontent,
                    'itempagetitle'   : itempagetitle,
                    'seqnum'          : seqnum
                }
            )

    print("Distinct release items: %s. Checking cross-matches" % len(grouped))

    artrows = []
    for key, value in grouped.items():
        if len(value) > 1:
            all_match = all([
                            value[0]['sitename'] == tmp['sitename']
                        and
                            value[0]['artistname'] == tmp['artistname']
                        and
                            value[0]['pageurl'] == tmp['pageurl']
                        and
                            value[0]['itempagecontent'] == tmp['itempagecontent']
                        and
                            value[0]['itempagetitle'] == tmp['itempagetitle']
                    for
                        tmp in value
                ])
            if not all_match:
                print("Not all match!")
                print(key)

        if (key[0], key[1]) in user_map:
            artrows.append({
                    'state'        : 'complete',
                    'errno'        : 0,
                    'artist_id'    : user_map[(key[0], key[1])],
                    'release_meta' : value[0]['pageurl'],
                    'fetchtime'    : datetime.datetime.utcfromtimestamp(value[0]['retreivaltime']),
                    'addtime'      : datetime.datetime.min,
                    'title'        : value[0]['itempagetitle'],
                    'content'      : value[0]['itempagecontent'],
                })

        else:
            raise RuntimeError("Missing artist/site combo: %s->%s" % (key[0], key[1]))

    print("Doing insert of table rows")
    op.bulk_insert(art_item_tbl, artrows)
    print("Requerying to get rowids so files can be cross-linked.")


    res = conn.execute('''
        SELECT
             id,
             artist_id,
             release_meta
        FROM art_item;
        ''')
    release_map = res.fetchall()

    release_ids = {}

    print("Processing requeries data.")
    for rid, artist_id, release_meta in release_map:
        art_site, art_username = user_reverse_map[artist_id]
        key = (art_site, art_username, release_meta)
        release_ids[key] = rid

    print("Requeried rows. Sorting file data")


    file_rows = []
    for key, values in grouped.items():
        rid = release_ids[key]
        for subfile in values:
            dlpath = subfile['downloadpath']
            num = subfile['seqnum']
            if dlpath:
                fname = os.path.split(dlpath)[-1]
            else:
                fname = None

            tmp = {
                'item_id'  : rid,
                'seqnum'   : num,
                'filename' : fname,
                'fspath'   : dlpath,
            }
            if fname:
                file_rows.append(tmp)

    print("Inserting file rows")

    op.bulk_insert(art_file_tbl, file_rows)

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    scrape_targets_tbl = op.create_table('scrape_targets',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('site_name', sa.Text(), nullable=False),
    sa.Column('artist_name', sa.Text(), nullable=False),
    sa.Column('uploadeh', sa.Boolean(), nullable=True),
    sa.Column('last_fetched', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_name', 'artist_name')
    )
    op.create_index(op.f('ix_scrape_targets_uploadeh'), 'scrape_targets', ['uploadeh'], unique=False)

    art_item_tbl = op.create_table('art_item',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('state', postgresql.ENUM('new', 'fetching', 'processing', 'complete', 'error', 'removed', 'disabled', 'specialty_deferred', 'specialty_ready', name='dlstate_enum'), nullable=False),
    sa.Column('errno', sa.Integer(), nullable=True),
    sa.Column('artist_id', sa.BigInteger(), nullable=True),
    sa.Column('release_meta', sa.Text(), nullable=False),
    sa.Column('fetchtime', sa.DateTime(), nullable=True),
    sa.Column('addtime', sa.DateTime(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['artist_id'], ['scrape_targets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('artist_id', 'release_meta')
    )
    op.create_index(op.f('ix_art_item_id'), 'art_item', ['id'], unique=False)
    op.create_index(op.f('ix_art_item_state'), 'art_item', ['state'], unique=False)

    art_file_tbl = op.create_table('art_file',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('seqnum', sa.Integer(), nullable=False),
    sa.Column('filename', sa.Text(), nullable=True),
    sa.Column('fspath', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['item_id'], ['art_item.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'seqnum')
    )
    op.create_index(op.f('ix_art_file_id'), 'art_file', ['id'], unique=False)

    art_tag_tbl = op.create_table('art_tag',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('tag', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['item_id'], ['art_item.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'tag')
    )
    op.create_index(op.f('ix_art_tag_id'), 'art_tag', ['id'], unique=False)

    ##########################################################################################
    ##########################################################################################

    conn = op.get_bind()
    res = conn.execute('''
            SELECT
             tablename
            FROM
             pg_catalog.pg_tables
            WHERE
             schemaname != 'pg_catalog'
            AND schemaname != 'information_schema';'''
        )
    have = res.fetchall()
    have = [tmp for tmp, in have]
    if 'retrieved_pages' in have:
        print("Have:", have)
        migrate_data()
    elif ('retrieved_pages', ) in have:
        print("Have:", have)
        migrate_data()

    ##########################################################################################
    ##########################################################################################

    print("Migration complete!")




def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_art_tag_id'), table_name='art_tag')
    op.drop_table('art_tag')
    op.drop_index(op.f('ix_art_file_id'), table_name='art_file')
    op.drop_table('art_file')
    op.drop_index(op.f('ix_art_item_state'), table_name='art_item')
    op.drop_index(op.f('ix_art_item_id'), table_name='art_item')
    op.drop_table('art_item')
    op.drop_index(op.f('ix_scrape_targets_uploadeh'), table_name='scrape_targets')
    op.drop_table('scrape_targets')
    ### end Alembic commands ###
