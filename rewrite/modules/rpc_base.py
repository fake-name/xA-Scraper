import sys
import time
import traceback
import queue
import datetime
import mprpc
import logging
import dill
import pprint

from settings import settings
import os

# import common.database as db
from rewrite import log_base


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
			unique_id      = None,
		):

	job = {
			'call'                 : call,
			'module'               : module,
			'args'                 : args,
			'kwargs'               : kwargs,
			'extradat'             : additionalData,
			'jobid'                : jobid,
			'dispatch_key'         : dispatchKey,
			'postDelay'            : postDelay,
			'serialize'            : True,
			'response_routing_key' : 'lowrate_response',
		}
	if unique_id is not None:
		job['unique_id'] = unique_id
	return job

class RemoteJobInterface(log_base.LoggerMixin):

	loggerPath = "Main.RemoteJobInterface"

	def __init__(self, interfacename, server_ip, server_port):
		self.interfacename = interfacename

		# Execute in self.rpc_client:
		for x in range(99999):
			try:
				# Cut-the-corners TCP Client:
				mp_conf = {"use_bin_type":True}
				self.rpc_client = mprpc.RPCClient(server_ip, server_port, pack_params=mp_conf)

				self.check_ok()
				return
			except Exception as e:
				if x > 3:
					raise e

	def get_job(self):
		try:
			j = self.rpc_client.call('getJob', self.interfacename)
			return j
		except Exception as e:
			raise e

	def get_job_nowait(self):
		try:
			j = self.rpc_client.call('getJobNoWait', self.interfacename)
			return j
		except Exception as e:
			raise e

	def put_feed_job(self, message):
		assert isinstance(message, (str, bytes, bytearray))
		self.rpc_client.call('putRss', message)

	def put_many_feed_job(self, messages):
		assert isinstance(messages, (list, set))
		self.rpc_client.call('putManyRss', messages)

	def put_job(self, job):
		self.rpc_client.call('putJob', self.interfacename, job)


	def check_ok(self):
		ret, bstr = self.rpc_client.call('checkOk')
		assert ret is True
		assert len(bstr) > 0

	def close(self):
		self.rpc_client.close()


class RpcMixin():


	def __init__(self):
		super().__init__()
		self.check_open_rpc_interface()
		self.log.info("RPC Interface initialized")

	def put_outbound_raw(self, raw_job):
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
			except BrokenPipeError:
				self.check_open_rpc_interface()
			except Exception as e:
				self.check_open_rpc_interface()
				errors += 1
				if errors > 5:
					raise e


	def put_outbound_fetch_job(self, jobid, joburl):
		self.log.info("Dispatching new fetch job")
		raw_job = buildjob(
			module         = 'WebRequest',
			call           = 'getItem',
			dispatchKey    = "rpc-system",
			jobid          = jobid,
			args           = [joburl],
			kwargs         = {},
			additionalData = {'mode' : 'fetch'},
			postDelay      = 0
		)

		self.put_outbound_raw(raw_job)

	def put_outbound_callable(self, jobid, serialized, meta={}, call_kwargs={}):
		self.log.info("Dispatching new callable job")
		call_kwargs_out = {'code_struct' : serialized}
		for key, value in call_kwargs.items():
			call_kwargs_out[key] = value

		raw_job = buildjob(
			module         = 'RemoteExec',
			call           = 'callCode',
			dispatchKey    = "rpc-system",
			jobid          = jobid,
			args           = [],
			kwargs         = call_kwargs_out,
			additionalData = meta,
			postDelay      = 0
		)

		self.put_outbound_raw(raw_job)

	# Note: The imports in *this* file determine what's available when
	# a rpc call is executed.

	def serialize_class(self, tgt_class, exec_method='go'):
		ret = {
			'source'      : dill.source.getsource(tgt_class),
			'callname'    : tgt_class.__name__,
			'exec_method' : exec_method,
		}
		return ret

	def deserialize_class(self, class_blob):
		assert 'source'      in class_blob
		assert 'callname'     in class_blob
		assert 'exec_method' in class_blob

		code = compile(class_blob['source'], "no filename", "exec")
		exec(code)
		cls_def = locals()[class_blob['callname']]
		# This call relies on the source that was exec()ed having defined the class
		# that will now be unserialized.
		return cls_def, class_blob['exec_method']




	def process_responses(self):
		# Something in the RPC stuff is resulting in a typeerror I don't quite
		# understand the source of. anyways, if that happens, just reset the RPC interface.
		try:
			return self.rpc_interface.get_job()
		except queue.Empty:
			return None

		except TypeError:
			self.check_open_rpc_interface()
			return None
		except KeyError:
			self.check_open_rpc_interface()
			return None


	def check_open_rpc_interface(self):
		if not hasattr(self, "rpc_interface"):
			self.rpc_interface = RemoteJobInterface("XA-RPC-Fetcher", settings['rpc-server']['address'], settings['rpc-server']['port'])
		try:
			if self.rpc_interface.check_ok():
				return


		except Exception:
			self.log.error("Failure when probing RPC interface")
			for line in traceback.format_exc().split("\n"):
				self.log.error(line)
			try:
				self.rpc_interface.close()
				self.log.warning("Closed interface due to connection exception.")
			except Exception:
				self.log.error("Failure when closing errored RPC interface")
				for line in traceback.format_exc().split("\n"):
					self.log.error(line)
			self.rpc_interface = RemoteJobInterface("XA-RPC-Fetcher", settings['rpc-server']['address'], settings['rpc-server']['port'])


