
from plugins.scrapers.da.daScrape import GetDA
from plugins.scrapers.px.pxScrape import GetPX
from plugins.scrapers.hf.hfScrape import GetHF
from plugins.scrapers.fa.faScrape import GetFA

import flags
import settings

import logSetup

import signal
import multiprocessing.managers


import sys

manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()

def go():

	namespace.run=True

	if len(sys.argv) < 2:
		print("Specify site to scrape ('da', 'fa', 'hf', 'px')")
		return


	site = sys.argv[1].lower()

	if site not in settings.settings['artSites']:
		print("Invalid site!")
		print("Please specify a *valid* site to scrape ('da', 'fa', 'hf', 'px')")
		return

	if site == "px":
		fetch = GetPX()
	elif site == "da":
		fetch = GetDA()
	elif site == "fa":
		fetch = GetFA()
	elif site == "hf":
		fetch = GetHF()
	else:
		raise ValueError("WAT?")

	print("Site", site)
	# fetch = GetDA()
	fetch.go(ctrlNamespace=namespace)



	# daGrabber.go([", "])



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

