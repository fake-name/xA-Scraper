
import sys
import multiprocessing
import contextlib
import threading

from settings import settings


from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

import time


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

import queue

# from settings import MAX_DB_SESSIONS
# from settings import DATABASE_IP            as C_DATABASE_IP
# from settings import DATABASE_DB_NAME       as C_DATABASE_DB_NAME
# from settings import DATABASE_USER          as C_DATABASE_USER
# from settings import DATABASE_PASS          as C_DATABASE_PASS

import traceback

# from flask import g
import flags

SQLALCHEMY_DATABASE_URI = 'postgresql://{user}:{passwd}@{host}:5432/{database}'.format(
	user     = settings['postgres']['username'],
	passwd   = settings['postgres']['password'],
	host     = settings['postgres']['address'],
	database = settings['postgres']['database']
	)


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

			print("INFO: Creating engine for process! Engine name: '%s'" % csid)
			ENGINES[csid] = create_engine(SQLALCHEMY_DATABASE_URI,
						isolation_level="REPEATABLE READ")
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

	print("Getting DB session (avail: %s, ID: '%s')" % (POOL.qsize(), csid))
	sess = POOL.get()
	return sess

def release_session(session):
	POOL.put(session)
	print("Returning db handle to pool. Handles available: %s" % (POOL.qsize(), ))

@contextlib.contextmanager
def context_sess():
	sess = checkout_session()
	try:
		yield sess
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




