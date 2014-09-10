

from settings import settings
import sys

import flags
import logSetup
import signal

import plugins.uploaders.eHentai.eHentaiUl
import multiprocessing.managers
#pylint: python3
#pylint: disable-msg=C0325


manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()
namespace.run=True


def go():

	ul = plugins.uploaders.eHentai.eHentaiUl.UploadEh()

	ul.go(ctrlNamespace=namespace)



def signal_handler(dummy_signal, dummy_frame):
	if flags.run:
		flags.run = False
		namespace.run=False
		print("Telling threads to stop")
	else:
		print("Multiple keyboard interrupts. Raising")
		raise KeyboardInterrupt

if __name__ == "__main__":
	signal.signal(signal.SIGINT, signal_handler)
	logSetup.initLogging()
	go()

