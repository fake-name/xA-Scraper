xA-Scraper
============

This is a automated tool for scraping content from a number of art sites:

- DeviantArt
- Patreon
- FurAffinity
- HentaFoundry
- Pixiv
- InkBunny
- SoFurry
- Weaslyl
- Newgrounds art galleries

To Add:

 - Artstation
 - https://beta.furrynetwork.com/?

Decrepit: 

- Tumblr art blogs


Checked so far:
 - hf, df, wy, ng, ib

Todo:
 - da, fa, pat, px

It also has grown a lot of other functions over time. It has a fairly complex,
interactive web-interface for browsing the local gallery mirrors, and a tool
for uploading galleries to aggregation sites (currently exhentai) is
in progress.

It has a lot in common with my other scraping system, [MangaCMS](https://github.com/fake-name/MangaCMS/). They both use
the same software stack (CherryPy, Pyramid, Mako, BS4). This is actually an older project, but I did not decide to release
it before now.

Dependencies:

 - Linux
 - Postgres >= 9.3 or Sqlite
 - CherryPy
 - Pyramid
 - Mako
 - BeautifulSoup 4
 - others

The backend can either use a local sqlite database (which has poor performance, particularly
when cold, but is *very* easy to set up), or a full postgresql instance.

Configuration is done via a file named `settings.py` which must be placed in the
repository root. `settings.base.py` is an example config to work from. 
In general, you will probably want to copy `settings.base.py` to `settings.py`, and then 
add your various usernames/password/database-config.

DB Backend is selected via the `USE_POSTGRESQL` parameter in `settings.py`. 

If using postgre, DB setup is left to the user. xA-Scraper requires it's own database, 
and the ability to make IP-based connections to the hosting PG instance. The connection 
information, DB name, and client name must be set in `settings.py`.

When using sqlite, you just have to specify the path to where you want the sqlite db to
be located (or you can use the default, which is `./sqlite_db.db`).

`settings.py` is also where the login information for the various plugins goes.

Disabling of select plugins can be accomplished by commenting out the appropriate
line in `main.py`. The `JOBS` list dictates the various scheduled scraper tasks 
that are placed into the scheduling system.

The preferred bootstrap method is to use `run.sh` from the repository root. It will
ensure the required packages are available (build-essential, libxml2 libxslt1-dev 
python3-dev libz-dev), and then install all the required python modules in a local 
virtualenv. Additonally, it checks if the virtualenv is present, so once it's created,
`./run.sh` will just source the venv, and run the scraper witout any reinstallation.

Currently, there are some aspects that need work. The artist selection system is currently a bit 
broken. Currently, there isn't a clean way to remove artists from the scrape list, though you can 
add or modify them.


## Notes:  

 - There have been reports that things are actively broken on non-linux platforms. Realistically, 
 all development is done on a Ubuntu 16.04 LTS install, and running on anything else is at 
 your own risk.

 - The Yiff-Party scraper requires significant external infrastructure, as it currently depends on
threading it's fetch requests through the [autotriever](https://github.com/fake-name/AutoTriever)
project. This depends on having both a publically available RabbitMQ instance, and 
an executing instance of the FetchAgent components of the [ReadableWebProxy](https://github.com/fake-name/ReadableWebProxy) 
fetch-agent RPC service on your local LAN.

 -FurAffinity has a login captcha. This requires you either manually log the FA scraper in 
(via the "Manual FA Login" facility in the web-interface), or you can use a automated captcha service.
Currently, the only solver service supported is the [2Captcha service](https://2captcha.com/).

 - **This is my oldest "maintained" project, and the codebase is commensuarately *horrible*.
Portions of it were designed and written while I was still learning python, so there
are a bunch of really terrible design decisons baked into the class structure, and 
much of the code just does stupid things.**


---


Anyways, Pictures!
	
These are a few DeviantArt Artists culled from the Reddit [ImaginaryLandscapes](http://www.reddit.com/r/ImaginaryLandscapes/) subreddit.

The web-interface has a lot of fancy mouseover preview stuff. Since this is primarily intended to run off a local network, bandwidth concerns are not too relevant, and I went a bit nuts with jQuery.

![Basic Popups](https://raw.githubusercontent.com/fake-name/xA-Scraper/gh-pages/Mouse1.gif)


There is also a somewhat experimental "gallery slice" viewing system, where horizontal mouse movement seeks through a spaced sub-set of each artist's images. The artist is determined by the row, and each horizontal 10 pixels is a different image.

![Fancy Popups](https://raw.githubusercontent.com/fake-name/xA-Scraper/gh-pages/Mouse2.gif)


Lastly, there is also a basic, chronological view of each artist's work, though it does support infinite-scrolling for their entire gallery. The scraper also preserves the description that preserves each item, and it is presented with the corresponding image.

