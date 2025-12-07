

import datetime
import logging
import threading
import copy

from sqlalchemy import Table

from sqlalchemy import Column
from sqlalchemy import Text
from sqlalchemy import DateTime
from sqlalchemy import Boolean
from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import BigInteger
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import Float
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Interval
from sqlalchemy import ForeignKey
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

import datetime
from sqlalchemy.types import Enum
import sqlalchemy_jsonfield

from sqlalchemy.ext.compiler import compiles


import cachetools

# from common.db_engine import session_context
from xascraper.database_calls import context_sess

import settings

# This is craptacularly retarded. Sqlite is retarded
# see https://bitbucket.org/zzzeek/sqlalchemy/issues/2074/map-biginteger-type-to-integer-to-allow
@compiles(BigInteger, 'sqlite')
def bi_c(element, compiler, **kw):
	return "INTEGER"


dlstate_enum   = Enum('new', 'fetching', 'processing', 'complete', 'error',  'cannot_view', 'removed', 'disabled', 'specialty_deferred', 'specialty_ready', 'not_set', name='dlstate_enum')

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


class ArtItem(Base):
	__versioned__ = {}

	__tablename__       = 'art_item'

	id                  = Column(BigInteger, primary_key = True, index = True)
	state               = Column(dlstate_enum, default='new', index=True, nullable=False)
	errno               = Column(Integer, default='0')

	artist_id           = Column(BigInteger, ForeignKey('scrape_targets.id'), nullable=False)
	release_meta        = Column(Text, nullable = False, index=True)

	fetchtime           = Column(DateTime, default=datetime.datetime.min)
	addtime             = Column(DateTime, default=datetime.datetime.utcnow)

	title               = Column(Text)
	content             = Column(Text)
	content_structured  = Column(sqlalchemy_jsonfield.JSONField())

	artist         = relationship("ScrapeTargets", backref='posts')
	files          = relationship("ArtFile", backref='item')
	tags           = relationship("ArtTags", backref='item')

	__table_args__ = (
		UniqueConstraint('artist_id', 'release_meta'),
		)


class ArtFile(Base):
	__tablename__     = 'art_file'
	id                = Column(BigInteger, primary_key = True, index = True)

	item_id           = Column(BigInteger, ForeignKey('art_item.id'), nullable=False)
	seqnum            = Column(Integer, default='0', nullable=False)
	file_meta         = Column(Text, default='')

	state             = Column(dlstate_enum, default='not_set')

	filename          = Column(Text)

	fspath            = Column(Text, nullable=False)

	__table_args__ = (
		UniqueConstraint('item_id', 'seqnum', 'file_meta'),
		)

class ArtTags(Base):
	__tablename__     = 'art_tag'
	id                = Column(BigInteger, primary_key = True, index = True)

	item_id           = Column(BigInteger, ForeignKey('art_item.id'), nullable=False)

	tag               = Column(Text)

	__table_args__ = (
		UniqueConstraint('item_id', 'tag'),
		)


# File table doesn't know anything about URLs, since they're kept in the
# WebPages table entirely.
class ScrapeTargets(Base):
	__tablename__ = 'scrape_targets'
	id              = Column(BigInteger, primary_key = True)
	site_name       = Column(Text,     nullable=False)
	artist_name     = Column(Text,     nullable=False, index=True)
	uploadeh        = Column(Boolean,  index = True, default=False, nullable=True)
	last_fetched    = Column(DateTime, nullable=False, default=datetime.datetime.min)

	extra_meta      = Column(sqlalchemy_jsonfield.JSONField())

	release_cnt     = Column(Integer, default='0')
	enabled         = Column(Boolean,  nullable=False, default=True)

	# posts           = relationship("ArtItem")

	in_progress     = Column(Boolean, default=False)

	__table_args__ = (
		UniqueConstraint('site_name', 'artist_name'),
		)



class ScraperStatus(Base):
	__tablename__     = 'scraper_status'
	id                = Column(BigInteger, primary_key = True, index = True)

	site_name          = Column(Text, nullable=False, unique=True, index=True)

	next_run          = Column(DateTime, nullable=False, default=datetime.datetime.min)
	prev_run          = Column(DateTime, nullable=False, default=datetime.datetime.min)
	prev_run_time     = Column(Interval, nullable=False, default=datetime.timedelta(0))
	is_running        = Column(Boolean,  nullable=False, default=False)

	status_text       = Column(Text)





##########################################################################################
##########################################################################################

KV_META_CACHE = cachetools.TTLCache(maxsize=5000, ttl=60 * 5)

kv_log = logging.getLogger("Main.KV_Store")

class KeyValueStore(Base):
	__tablename__ = 'key_value_store'

	id          = Column(BigInteger, primary_key=True)

	key    = Column(Text, nullable=False, index=True, unique=True)
	value  = Column(sqlalchemy_jsonfield.JSONField())


def get_from_db_key_value_store(key):
	global KV_META_CACHE
	if key in KV_META_CACHE:
		kv_log.info("Getting '%s' from kv store in RAM", key)
		return KV_META_CACHE[key]

	kv_log.info("Getting '%s' from kv store in DB", key)
	with context_sess() as sess:
		have = sess.query(KeyValueStore).filter(KeyValueStore.key == key).scalar()
		if have:
			kv_log.info("KV store had entry")
			ret = have.value
		else:
			kv_log.info("KV store did not have entry")
			ret = {}

		sess.commit()

	return ret


def set_in_db_key_value_store(key, new_data):
	global KV_META_CACHE

	new_s = str(new_data)
	if len(new_s) > 40:
		new_s = new_s[:35] + "..."

	kv_log.info("Setting kv key '%s' to '%s'", key, new_s)
	if key in KV_META_CACHE:
		if KV_META_CACHE[key] == new_data:
			return


	with context_sess() as sess:
		have = sess.query(KeyValueStore).filter(KeyValueStore.key == key).scalar()
		if have:
			if have.value != new_data:
				kv_log.info("Updating item: '%s', '%s'", have, have.key)
				kv_log.info("	old -> %s", have.value)
				kv_log.info("	new -> %s", new_s)
				have.value = new_data
			else:
				kv_log.info("Item has not changed. Nothing to do!")
		else:
			kv_log.info("New item: '%s', %s", key, new_s)
			new = KeyValueStore(
				key   = key,
				value = new_data,
				)
			sess.add(new)

		sess.commit()

	try:
		KV_META_CACHE[key] = copy.copy(new_data)
	except KeyError:
		KV_META_CACHE = cachetools.TTLCache(maxsize=5000, ttl=60 * 5)
		KV_META_CACHE[key] = copy.copy(new_data)


##########################################################################################
##########################################################################################




import sqlalchemy as sa
sa.orm.configure_mappers()
