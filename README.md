xA-Scraper
============

This is a automated tool for scraping content from a number of art sites:

- DeviantArt
- FurAffinity
- HentaFoundry
- Pixiv
- Tumblr art blogs
- SoFurry
- Weaslyl

To Add:

 - https://beta.furrynetwork.com/?

It also has grown a lot of other functions over time. It has a fairly complex,
interactive web-interface for browsing the local gallery mirrors, and a tool
for uploading galleries to aggregation sites (currently exhentai) is
in progress.

It has a lot in common with my other scraping system, [MangaCMS](https://github.com/fake-name/MangaCMS/). They both use
the same software stack (CherryPy, Pyramid, Mako, BS4). This is actually an older project, but I did not decide to release
it before now.

Dependencies:

 - CherryPy
 - Pyramid
 - Mako
 - BeautifulSoup 4

Currently, there are some aspects that need work. The artist selection system is currently a bit broken, as I was
in the process of converting it from being based on text-files to being stored in the database. Currently, there isn't a clean way to remove artists from the scrape list, though you can add or modify them.


---


Anyways, Pictures!
	
These are a few DeviantArt Artists culled from the Reddit [ImaginaryLandscapes](http://www.reddit.com/r/ImaginaryLandscapes/) subreddit.

The web-interface has a lot of fancy mouseover preview stuff. Since this is primarily intended to run off a local network, bandwidth concerns are not too relevant, and I went a bit nuts with jQuery.

![Basic Popups](https://raw.githubusercontent.com/fake-name/xA-Scraper/gh-pages/Mouse1.gif)


There is also a somewhat experimental "gallery slice" viewing system, where horizontal mouse movement seeks through a spaced sub-set of each artist's images. The artist is determined by the row, and each horizontal 10 pixels is a different image.

![Fancy Popups](https://raw.githubusercontent.com/fake-name/xA-Scraper/gh-pages/Mouse2.gif)


Lastly, there is also a basic, chronological view of each artist's work, though it does support infinite-scrolling for their entire gallery. The scraper also preserves the description that preserves each item, and it is presented with the corresponding image.

