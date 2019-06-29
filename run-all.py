
import plugins.scrapers.fa.faScrape
import plugins.scrapers.px.pxScrape
import plugins.scrapers.ib.ibScrape
import plugins.scrapers.hf.hfScrape
import plugins.scrapers.da.daScrape
import plugins.scrapers.wy.wyScrape

import flags

import logSetup

import signal
import multiprocessing.managers


manager = multiprocessing.managers.SyncManager()
manager.start()
namespace = manager.Namespace()
namespace.run=True

def go():


	# daGrabber = plugins.scrapers.da.daScrape.GetDA()
	# daGrabber.go(ctrlNamespace=namespace)


	# faGrabber = plugins.scrapers.fa.faScrape.GetFA()
	# faGrabber.go(ctrlNamespace=namespace)


	# ibGrab = plugins.scrapers.ib.ibScrape.GetIb()
	# ibGrab.go(ctrlNamespace=namespace)


	# hfGrabber = plugins.scrapers.hf.hfScrape.GetHF()
	# hfGrabber.go(ctrlNamespace=namespace)


	# daGrabber = plugins.scrapers.da.daScrape.GetDA()
	# daGrabber.go(ctrlNamespace=namespace)


	# wyGrab = plugins.scrapers.wy.wyScrape.GetWy()
	# wyGrab.go(ctrlNamespace=namespace)

	pxGrabber = plugins.scrapers.px.pxScrape.GetPX()
	pxGrabber.checkLogin()

	pxGrabber.go(ctrlNamespace=namespace)



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

