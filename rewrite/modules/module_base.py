import sys
import time
import traceback
import queue
import datetime

import bsonrpc.exceptions
import os

# import common.database as db
from rewrite import log_base
from rewrite import get_rpc_interface


########################################################################################################################
#
#	##     ##    ###    #### ##    ##     ######  ##          ###     ######   ######
#	###   ###   ## ##    ##  ###   ##    ##    ## ##         ## ##   ##    ## ##    ##
#	#### ####  ##   ##   ##  ####  ##    ##       ##        ##   ##  ##       ##
#	## ### ## ##     ##  ##  ## ## ##    ##       ##       ##     ##  ######   ######
#	##     ## #########  ##  ##  ####    ##       ##       #########       ##       ##
#	##     ## ##     ##  ##  ##   ###    ##    ## ##       ##     ## ##    ## ##    ##
#	##     ## ##     ## #### ##    ##     ######  ######## ##     ##  ######   ######
#
########################################################################################################################




def buildjob(
			module,
			call,
			dispatchKey,
			jobid,
			args           = [],
			kwargs         = {},
			additionalData = None,
			postDelay      = 0,
			extra_keys     = {},
			unique_id      = None,
		):

	job = {
			'call'         : call,
			'module'       : module,
			'args'         : args,
			'kwargs'       : kwargs,
			'extradat'     : additionalData,
			'jobid'        : jobid,
			'dispatch_key' : dispatchKey,
			'postDelay'    : postDelay,
		}
	if unique_id is not None:
		job['unique_id'] = unique_id
	return job



class RpcPluginBase(log_base.LoggerMixin):


	def __init__(self, job_queue, run_flag):
		super().__init__()


	def put_outbound_job(self, jobid, joburl):
		self.active_jobs += 1
		self.log.info("Dispatching new job")
		raw_job = buildjob(
			module         = 'WebRequest',
			call           = 'getItem',
			dispatchKey    = "fetcher",
			jobid          = jobid,
			args           = [joburl],
			kwargs         = {},
			additionalData = {'mode' : 'fetch'},
			postDelay      = 0
		)

		# Recycle the rpc interface if it ded
		errors = 0
		while 1:
			try:
				self.rpc_interface.put_job(raw_job)
				return
			except TypeError:
				self.check_open_rpc_interface()
			except KeyError:
				self.check_open_rpc_interface()
			except bsonrpc.exceptions.BsonRpcError as e:
				errors += 1
				self.check_open_rpc_interface()
				if errors > 3:
					raise e
				else:
					self.log.warning("Exception in RPC request:")
					for line in traceback.format_exc().split("\n"):
						self.log.warning(line)



	def process_responses(self):
		while 1:

			# Something in the RPC stuff is resulting in a typeerror I don't quite
			# understand the source of. anyways, if that happens, just reset the RPC interface.
			try:
				tmp = self.rpc_interface.get_job()
			except queue.Empty:
				return

			except TypeError:
				self.check_open_rpc_interface()
				return
			except KeyError:
				self.check_open_rpc_interface()
				return

			except bsonrpc.exceptions.ResponseTimeout:
				self.check_open_rpc_interface()
				return


			if tmp:
				self.active_jobs -= 1
				self.jobs_in += 1
				if self.active_jobs < 0:
					self.active_jobs = 0
				self.log.info("Job response received. Jobs in-flight: %s (qsize: %s)", self.active_jobs, self.normal_out_queue.qsize())
				self.last_rx = datetime.datetime.now()

				self.__blocking_put(tmp)
			else:
				self.print_mod += 1
				if self.print_mod > 20:
					self.log.info("No job responses available.")
					self.print_mod = 0
				time.sleep(1)
				break

	def check_open_rpc_interface(self):
		if not hasattr(self, "rpc_interface"):
			self.rpc_interface = get_rpc_interface.RemoteJobInterface("RPC-Fetcher")
		try:
			if self.rpc_interface.check_ok():
				return


		except Exception:
			self.log.error("Failure when probing RPC interface")
			for line in traceback.format_exc().split("\n"):
				self.log.error(line)
			try:
				self.rpc_interface.close()
				self.log.info("Closed interface due to connection exception.")
			except Exception:
				self.log.error("Failure when closing errored RPC interface")
				for line in traceback.format_exc().split("\n"):
					self.log.error(line)
			self.rpc_interface = get_rpc_interface.RemoteJobInterface("RPC-Fetcher")
