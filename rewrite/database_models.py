

import settings

from sqlalchemy import Table

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
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.dialects.postgresql import JSON



dlstate_enum   = ENUM('new', 'fetching', 'processing', 'complete', 'error', 'removed', 'disabled', 'specialty_deferred', 'specialty_ready', name='dlstate_enum')

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


class ArtItem(Base):
	__versioned__ = {}

	__tablename__     = 'art_item'

	id                = Column(BigInteger, primary_key = True, index = True)
	state             = Column(dlstate_enum, default='new', index=True, nullable=False)
	errno             = Column(Integer, default='0')

	artist_id         = Column(BigInteger, ForeignKey('scrape_targets.id'), nullable=False)
	release_meta      = Column(Text, nullable = False, index=True)

	fetchtime         = Column(DateTime, default=datetime.datetime.min)
	addtime           = Column(DateTime, default=datetime.datetime.utcnow)

	title             = Column(Text)
	content           = Column(Text)

	artist         = relationship("ScrapeTargets")
	files          = relationship("ArtFile")
	tags           = relationship("ArtTags")

	__table_args__ = (
		UniqueConstraint('artist_id', 'release_meta'),
		)


class ArtFile(Base):
	__tablename__     = 'art_file'
	id                = Column(BigInteger, primary_key = True, index = True)

	item_id           = Column(BigInteger, ForeignKey('art_item.id'), nullable=False)
	seqnum       = Column(Integer, default='0', nullable=False)

	filename     = Column(Text)

	fspath       = Column(Text, nullable=False)

	__table_args__ = (
		UniqueConstraint('item_id', 'seqnum'),
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

	extra_meta      = Column(JSON)

	release_cnt     = Column(Integer, default='0')

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




import sqlalchemy as sa
sa.orm.configure_mappers()
