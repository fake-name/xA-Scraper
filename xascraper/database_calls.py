
import sys
import multiprocessing
import logging
import contextlib
import threading
import sqlalchemy.exc

import orjson
from settings import settings
from settings import SQLALCHEMY_DATABASE_URI


from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

import time


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

import queue

import traceback

# from flask import g
import flags



SESSIONS = {}
ENGINES  = {}
POOL    = None


ENGINE_LOCK = multiprocessing.Lock()
SESSION_LOCK = multiprocessing.Lock()

def get_engine():
	cpid = multiprocessing.current_process().name
	ctid = threading.current_thread().name
	csid = "{}-{}".format(cpid, ctid)
	if not csid in ENGINES:
		with ENGINE_LOCK:
			# Check if the engine was created while we were
			# waiting on the lock.
			if csid in ENGINES:
				return ENGINES[csid]
			iso_level = "REPEATABLE READ"
			if SQLALCHEMY_DATABASE_URI.startswith("sqlite://"):
				iso_level = 'SERIALIZABLE'
			print("INFO: Creating engine for process! Engine name: '%s'" % csid)
			ENGINES[csid] = create_engine(SQLALCHEMY_DATABASE_URI,
						isolation_level=iso_level,

							json_serializer   = lambda x: orjson.dumps(x).decode('utf-8'),
							json_deserializer = orjson.loads,
						)
						# isolation_level="READ COMMITTED")

	return ENGINES[csid]

def __check_create_pool():
	global POOL
	if not POOL:
		print("Creating pool")
		POOL = queue.Queue()
		for dummy_x in range(10):
			POOL.put(scoped_session(sessionmaker(bind=get_engine(), autoflush=False, autocommit=False))())


def checkout_session():
	__check_create_pool()

	cpid = multiprocessing.current_process().name
	ctid = threading.current_thread().name
	csid = "{}-{}".format(cpid, ctid)

	# print("Getting DB session (avail: %s, ID: '%s')" % (POOL.qsize(), csid))
	sess = POOL.get()
	return sess

def release_session(session):
	POOL.put(session)
	# print("Returning db handle to pool. Handles available: %s" % (POOL.qsize(), ))

tx_logger = logging.getLogger("Main.DbContext")

@contextlib.contextmanager
def context_sess():
	sess = checkout_session()
	try:
		yield sess

		# Don't ever allow open queries
		sess.commit()

	except sqlalchemy.exc.InvalidRequestError:
		tx_logger.warning("context_sess() -> InvalidRequest error!")
		for line in traceback.format_exc().split("\n"):
			tx_logger.warning(line)
		sess.rollback()
		raise

	except sqlalchemy.exc.OperationalError:
		tx_logger.warning("context_sess() -> InvalidRequest error!")
		for line in traceback.format_exc().split("\n"):
			tx_logger.warning(line)
		sess.rollback()
		raise

	except sqlalchemy.exc.IntegrityError:
		tx_logger.warning("context_sess() -> Integrity error!")
		for line in traceback.format_exc().split("\n"):
			tx_logger.warning(line)
		sess.rollback()
		raise


	finally:
		release_session(sess)

@contextlib.contextmanager
def context_cursor():
	sess = checkout_session()
	try:
		yield sess.cursor()
	finally:
		release_session(sess)



def get_db_session(postfix=""):

	cpid = multiprocessing.current_process().name
	ctid = threading.current_thread().name
	csid = "{}-{}-{}".format(cpid, ctid, postfix)

	# print("Getting session for thread: %s" % csid)
	# print(traceback.print_stack())
	# print("==========================")


	if not csid in SESSIONS:
		with SESSION_LOCK:

			# check if the session was created while
			# we were waiting for the lock
			if csid in SESSIONS:
				# Reset the "last used" time on the handle
				SESSIONS[csid][0] = time.time()
				return SESSIONS[csid][1]

			SESSIONS[csid] = [time.time(), scoped_session(sessionmaker(bind=get_engine(), autoflush=False, autocommit=False))()]
			# print("Creating database interface:", SESSIONS[csid])

			# Delete the session that's oldest.
			if len(SESSIONS) > MAX_DB_SESSIONS:
				print("WARN: More then %s active sessions! Deleting oldest session to prevent session contention." % MAX_DB_SESSIONS)
				maxsz = sys.maxsize
				to_delete = None
				for key, value in SESSIONS.items():
					if value[0] < maxsz:
						to_delete = key
						maxsz = value[0]
				if to_delete:
					del SESSIONS[to_delete]

	# Reset the "last used" time on the handle
	SESSIONS[csid][0] = time.time()
	return SESSIONS[csid][1]

def delete_db_session(postfix=""):
	cpid = multiprocessing.current_process().name
	ctid = threading.current_thread().name
	csid = "{}-{}-{}".format(cpid, ctid, postfix)


	# print("Releasing session for thread: %s" % csid)
	# print(traceback.print_stack())
	# print("==========================")

	if csid in SESSIONS:
		with SESSION_LOCK:
			# check if the session was created while
			# we were waiting for the lock
			if not csid in SESSIONS:
				return
			SESSIONS[csid][1].close()
			del SESSIONS[csid]
			# print("Deleted session for id: ", csid)


# import traceback
# traceback.print_stack()




