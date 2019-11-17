
import xascraper.modules.da.daScrape as das
import xascraper.modules.fa.faScrape as fas
import xascraper.modules.hf.hfScrape as hfs
import xascraper.modules.px.pxScrape as pxs
import xascraper.modules.wy.wyScrape as wys
import xascraper.modules.ib.ibScrape as ibs
import xascraper.modules.sf.sfScrape as sfs
import xascraper.modules.ng.ngScrape as ngs
import xascraper.modules.ay.ayScrape as ays
import xascraper.modules.artstation.asScrape as ass
import xascraper.modules.twit.twitScrape as twits
import xascraper.modules.tumblr.tumblrScrape as tus
import xascraper.modules.patreon.patreonScrape as pts
import xascraper.modules.yiff_party.yiff_scrape as yps

from settings import settings


PLUGINS =[
	fas.GetFA,
	hfs.GetHF,
	wys.GetWy,
	ibs.GetIb,
	pxs.GetPX,
	sfs.GetSf,
	pts.GetPatreon,
	das.GetDA,
	ngs.GetNg,
	ays.GetAy,
	ass.GetAs,
	yps.GetYp,
	tus.GetTumblr,
	twits.GetTwit,
]

# Plugins that have no config have cls.validate_config() return None
# So yes, we have a tri-state boolean, and it's gross.
JOBS          = [cls.get_config(settings) for cls in PLUGINS if cls.validate_config(settings) == True]
JOBS_DISABLED = [cls.get_config(settings) for cls in PLUGINS if cls.validate_config(settings) == False]
JOBS_NO_CONF  = [cls                      for cls in PLUGINS if cls.validate_config(settings) == None]

