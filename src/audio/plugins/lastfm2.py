# -*- coding: iso-8859-1 -*-
# -----------------------------------------------------------------------
# 
# -----------------------------------------------------------------------
# $Id$
#
# Notes:
# Todo:
#
# -----------------------------------------------------------------------
# Freevo - A Home Theater PC framework
# Copyright (C) 2002 Krister Lagerstrom, et al.
# Please see the file freevo/Docs/CREDITS for a complete list of authors.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MER-
# CHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# -----------------------------------------------------------------------


import sys, os, time
import md5, urllib, urllib2

from kaa import Timer

import config
import plugin
from menu import MenuItem, Menu
from audio.audioitem import AudioItem
from audio.player import PlayerGUI
from util import feedparser
if sys.hexversion >= 0x2050000:
    from xml.etree.cElementTree import XML
else:
    try:
        from cElementTree import XML
    except ImportError:
        from elementtree.ElementTree import XML


class PluginInterface(plugin.MainMenuPlugin):
    """
    Last FM player client

    To activate this plugin, put the following in your local_conf.py:

    | plugin.activate('audio.lastfm')
    | LASTFM_USER = '<last fm user name>'
    | LASTFM_PASS = '<last fm password>'
    | LASTFM_MPLAYER_AF_TRACK = True
    | LASTFM_LOCATIONS = [
    |     ('Last Fm - Neighbours', 'lastfm://user/%s/neighbours' % LASTFM_USER),
    |     ('Last FM - Jazz', 'lastfm://globaltags/jazz'),
    |     ('Last FM - Rock', 'lastfm://globaltags/rock'),
    |     ('Last FM - Oldies', 'lastfm://globaltags/oldies'),
    |     ('Last FM - Pop', 'lastfm://globaltags/pop'),
    |     ('Last FM - Norah Jones', 'lastfm://artist/norah jones')
    | ]

    Events sent to lastfm:

    | RIGHT - skip song
    | 1     - send to lastfm LOVE song
    | 9     - send to lastfm BAN song
    """
    def __init__(self):
        _debug_('PluginInterface.__init__()', 2)
        if not config.LASTFM_USER or not config.LASTFM_PASS:
            self.reason = 'LASTFM_USER or LASTFM_PASS not set'
            return
        plugin.MainMenuPlugin.__init__(self)
    def config(self):
        """
        freevo plugins -i audio.freevo returns the info
        """
        _debug_('config()', 2)
        return [
            ('LASTFM_USER', None, 'User name for www.last.fm'),
            ('LASTFM_PASS', None, 'Password for www.last.fm'),
            ('LASTFM_LANG', 'en', 'Language of last fm metadata (cn,de,en,es,fr,it,jp,pl,ru,sv,tr)'),
            #('LASTFM_MPLAYER_AF_TRACK', False, 'Set to True if using mplayer\'s -af track'),
            ('LASTFM_LOCATIONS', [], 'LastFM locations')
        ]


    def items(self, parent):
        _debug_('items(parent=%r)' % (parent,), 2)
        return [ LastFMMainMenuItem(parent) ]



class LastFMError(Exception):
    def __init__(self, why):
        Exception.__init__(self)
        self.why = why



class LastFMMainMenuItem(MenuItem):
    """
    this is the item for the main menu and creates the list
    of commands in a submenu.
    """
    def __init__(self, parent):
        _debug_('LastFMMainMenuItem.__init__(parent=%r)' % (parent,), 2)
        MenuItem.__init__(self, parent, arg='audio', skin_type='radio')
        self.name = _('Last FM')
        self.webservices = LastFMWebServices()


    def actions(self):
        """return a list of actions for this item"""
        _debug_('actions()', 2)
        return [ (self.create_stations_menu, 'stations') ]


    def create_stations_menu(self, arg=None, menuw=None):
        _debug_('create_stations_menu(arg=%r, menuw=%r)' % (arg, menuw), 2)
        lfm_items = []
        self.webservices._login()
        for lfm_station in config.LASTFM_LOCATIONS:
            name, station = lfm_station
            lfm_item = LastFMItem(self, name, station, self.webservices)
            lfm_items += [ lfm_item ]
        if not lfm_items:
            lfm_items += [MenuItem(_('Invalid LastFM Session!'), menuw.goto_prev_page, 0)]
        lfm_menu = Menu(_('Last FM'), lfm_items)
        #rc.app(None)
        menuw.pushmenu(lfm_menu)
        menuw.refresh()
 


class LastFMItem(AudioItem):
    """
    This is the class that actually runs the commands. Eventually
    hope to add actions for different ways of running commands
    and for displaying stdout and stderr of last command run.
    """
    def __init__(self, parent, name, station, webservices):
        print 'LastFMItem.__init__(parent=%r, name=%r, station=%r, webservices=%r)' % \
            (parent, name, station, webservices)
        #self.image = None
        #AudioItem.__init__(self, 'http://', parent, name)
        AudioItem.__init__(self, station, parent, name)
        self.station = station
        self.webservices = webservices
        self.xspf = LastFMXSPF()
        self.feed = None
        self.entry = None


    def actions(self):
        """
        return a list of actions for this item
        """
        print 'LastFMItem.actions()'
        self.feed = self.xspf.parse(self.webservices.request_xspf())
        self.entry = 0
        items = [ (self.play, _('Listen to LastFM Station')) ]
        return items


    def play(self, arg=None, menuw=None):
        """
        Play the current playing
        """
        import pprint
        print 'LastFMItem.play(arg=%r, menuw=%r)' % (arg, menuw)
        self.menuw = menuw
        pprint.pprint(self.__dict__)
        entry = self.feed.entries[self.entry]
        print entry
        self.album = entry.album
        self.artist = entry.artist
        self.title = entry.title
        self.length = entry.duration
        self.image = self.webservices.download_cover(entry.image_url)
        self.url = entry.location_url
        self.player = PlayerGUI(self, menuw)
        error = self.player.play()
        if error and menuw:
            AlertBox(text=error).show()
            rc.post_event(rc.PLAY_END)


    def stop(self, arg=None, menuw=None):
        """
        Stop the current playing
        """
        print 'LastFMItem.stop(arg=%r, menuw=%r)' % (arg, menuw)
        self.player.stop()



class LastFMWebServices:
    """
    Interface to LastFM web-services
    """
    _version = '1.1.2'

    def __init__(self):
        _debug_('LastFMWebServices.__init__()', 2)
        self.logincachefilename = os.path.join(config.FREEVO_CACHEDIR, 'lastfm.session')
        try:
            self.cachefd = open(self.logincachefilename, 'r')
            self.session = self.cachefd.readline().strip('\n')
            self.stream_url = self.cachefd.readline().strip('\n')
            self.base_url = self.cachefd.readline().strip('\n')
            self.base_path = self.cachefd.readline().strip('\n')
        except IOError, why:
            self._login()


    def _urlopen(self, url, data=None, lines=True):
        """
        Wrapper to see what is sent and received
        When lines is true then the reply is returned as a list of lines,
        otherwise it is returned as a block.

        @param url: Is the URL to read.
        @param data: Is the POST data.
        @param lines: return a list of lines, otherwise data block.
        @returns: reply from request
        """
        _debug_('url=%r, data=%r' % (url, data), 1)
        print 'DJW:url=%r, data=%r' % (url, data)
        if lines:
            reply = []
            try:
                lines = urllib.urlopen(url, data).readlines()
                if lines is None:
                    return []
                for line in lines:
                    reply.append(line.strip('\n'))
            except Exception, why:
                _debug_('%s: %s' % (url, why), DWARNING)
                raise
            _debug_('reply=%r' % (reply,), 1)
            #DJW#
            import pprint
            pprint.pprint(lines)
            #DJW#
            return reply
        else:
            reply = ''
            try:
                reply = urllib.urlopen(url, data).read()
            except Exception, why:
                _debug_('%s: %s' % (url, why), DWARNING)
                raise
            _debug_('reply=%r' % (reply,), 1)
            return reply


    def _login(self, arg=None):
        """Read session and stream url from ws.audioscrobbler.com"""
        _debug_('login(arg=%r)' % (arg,), 2)
        username = config.LASTFM_USER
        password_txt = config.LASTFM_PASS
        password = md5.new(config.LASTFM_PASS)
        login_url='http://ws.audioscrobbler.com/radio/handshake.php' + \
            '?version=%s&platform=linux' % (LastFMWebServices._version) + \
            '&username=%s&passwordmd5=%s' % (config.LASTFM_USER, password.hexdigest()) + \
            '&debug=0&language=%s' % (config.LASTFM_LANG)
        stream_url = ''

        try:
            lines = self._urlopen(login_url)
            for line in lines:
                print line
                # this is a bit dangerous if a variable clashes
                exec('self.%s = "%s"' % tuple(line.split('=', 1)))
            # Save the lastfm session information
            fd = open(self.logincachefilename, 'w')
            print >>fd, self.session
            print >>fd, self.stream_url
            print >>fd, self.base_url
            print >>fd, self.base_path
            fd.close()
        except IOError, why:
            self.session = ''
            self.stream_url = ''
            self.base_url = ''
            self.base_path = ''


    def request_xspf(self):
        """Request a XSPF (XML Shareable Playlist File)"""
        _debug_('LastFMWebServices.request_xspf()', 2)
        print 'request_xspf()'
        if not self.session:
            self._login()
        request_url = 'http://%s%s/xspf.php?sk=%s&discovery=0&desktop=%s' % \
            (self.base_url, self.base_path, self.session, LastFMWebServices._version)
        return self._urlopen(request_url, lines=False)


    def adjust_station(self, station_url):
        """Change Last FM Station"""
        _debug_('adjust_station(station_url=%r)' % (station_url,), 2)
        if not self.session:
            self._login()
        tune_url = 'http://ws.audioscrobbler.com/radio/adjust.php?session=%s&url=%s&debug=0' % \
            (self.session, station_url)
        try:
            for x in self._urlopen(tune_url):
                if re.search('response=OK', x):
                    return True
            return False
        except IOError, why:
            return None


    def now_playing(self):
        """
        Return Song Info and album Cover
        """
        _debug_('now_playing()', 2)
        if not self.session:
            self._login()
        info_url = 'http://ws.audioscrobbler.com/radio/np.php?session=%s&debug=0' % (self.session,)
        return self._urlopen(info_url)


    def download_cover(self, pic_url):
        """Download album Cover to freevo cache directory"""
        _debug_('download_cover(pic_url=%r)' % (pic_url,), 2)

        os.system('rm -f %s/lfmcover_*.jpg' % config.FREEVO_CACHEDIR)
        if not self.session:
            self._login()
        pic_file = self._urlopen(pic_url, lines=False)
        try:
            savefile = os.path.join(config.FREEVO_CACHEDIR, 'lfmcover_'+str(time.time())+'.jpg')
            save = open(savefile, 'w')
            try:
                print >>save, pic_file
                return savefile
            finally:
                save.close()
        except IOError:
            return None


    def skip(self):
        """Skip song"""
        _debug_('skip()', 2)
        if not self.session:
            self._login
        skip_url = 'http://ws.audioscrobbler.com/radio/control.php?session=%s&command=skip&debug=0' % \
            (self.session)
        return self._urlopen(skip_url)


    def love(self):
        """Send "Love" information to audioscrobbler"""
        _debug_('love()', 2)
        if not self.session:
            self._login
        love_url = 'http://ws.audioscrobbler.com/radio/control.php?session=%s&command=love&debug=0' % \
            (self.session)
        return self._urlopen(love_url)


    def ban(self):
        """Send "Ban" information to audioscrobbler"""
        _debug_('ban()', 2)
        if not self.session:
            self._login
        ban_url = 'http://ws.audioscrobbler.com/radio/control.php?session=%s&command=ban&debug=0' % \
            (self.session)
        return self._urlopen(ban_url)


    def test_user_pass(self):
        """
        Test User/Pass

        This way you can check, whether a user/pass is valid.

        http://ws.audioscrobbler.com/ass/pwcheck.php?
            time=[TS]&username=[USER]&auth=[AUTH1]&auth2=[AUTH2]&defaultplayer=[PLAYER]

        Variables:

        * TS: Unix timestamp of the current time.
        * USER: Username.
        * AUTH1: md5( md5(password) + Timestamp), An md5 sum of an md5 sum of the password, plus the timestamp as salt.
        * AUTH2: Second possible Password. The client uses md5( md5(toLower(password)) + Timestamp)
        * PLAYER: See Appendix 
        """
        return True



class LastFMXSPF:
    """
    Analyse the XSPF (spiff) XML Sharable Playlist File feed using ElementTree

    XSPF is documented at U{http://www.xspf.org/quickstart/}
    """
    _LASTFM_NS = 'http://www.audioscrobbler.net/dtd/xspf-lastfm/'

    def __init__(self):
        self.entries = []
        self.feed = feedparser.FeedParserDict()


    def parse(self, xml):
        """
        Parse the XML feed
        """
        try:
            tree = XML(xml)
        except SyntaxError:
            raise LastFMError(xml)
        title = tree.find('title')
        self.feed.title = title is not None and title.text or u''
        for link_elem in tree.findall('link'):
            for k, v in link_elem.items():
                if k == 'rel' and v == 'http://www.last.fm/skipsLeft':
                    self.feed.skips_left = int(link_elem.text)
        tracklist = tree.find('trackList')
        if tracklist:
            for track_elem in tracklist.findall('track'):
                track = feedparser.FeedParserDict()
                title = track_elem.find('title')
                track.title = title is not None and title.text or u''
                album = track_elem.find('album')
                track.album = album is not None and album.text or u''
                artist = track_elem.find('creator')
                track.artist = artist is not None and artist.text or u''
                location_url = track_elem.find('location')
                track.location_url = location_url is not None and location_url.text or u''
                image_url = track_elem.find('image')
                track.image_url = image_url is not None and image_url.text or u''
                duration_ms = track_elem.find('duration')
                track.duration = duration_ms is not None and int(float(duration_ms.text)/1000.0+0.5) or 0
                self.entries.append(track)
        return self
