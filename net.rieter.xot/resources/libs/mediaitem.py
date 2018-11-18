# coding=utf-8
#===============================================================================
# LICENSE Retrospect-Framework - CC BY-NC-ND
#===============================================================================
# This work is licenced under the Creative Commons
# Attribution-Non-Commercial-No Derivative Works 3.0 Unported License. To view a
# copy of this licence, visit http://creativecommons.org/licenses/by-nc-nd/3.0/
# or send a letter to Creative Commons, 171 Second Street, Suite 300,
# San Francisco, California 94105, USA.
#===============================================================================

import datetime
import time
import random

import xbmc
import xbmcgui

from addonsettings import AddonSettings
from logger import Logger
from helpers.htmlentityhelper import HtmlEntityHelper
from helpers.encodinghelper import EncodingHelper
from helpers.languagehelper import LanguageHelper
from streams.adaptive import Adaptive
from proxyinfo import ProxyInfo


class MediaItem:
    """Main class that represent items that are retrieved in XOT. They are used
    to fill the lists and have MediaItemParts which have MediaStreams in this
    hierarchy:

    MediaItem
        +- MediaItemPart
        |    +- MediaStream
        |    +- MediaStream
        |    +- MediaStream
        +- MediaItemPart
        |    +- MediaStream
        |    +- MediaStream
        |    +- MediaStream

    """

    LabelTrackNumber = "TrackNumber"

    def __dir__(self):
        """ Required in order for the Pickler().Validate to work! """
        return ["name",
                "url",
                "actionUrl",
                "MediaItemParts",
                "description",
                "thumb",
                "fanart",
                "icon",
                "__date",
                "__timestamp",
                "type",
                "dontGroup",
                "isLive",
                "isGeoLocked",
                "isDrmProtected",
                "isPaid",
                "__infoLabels",
                "complete",
                "downloaded",
                "downloadable",
                "items",
                "HttpHeaders",
                "rating",
                "guid",
                "guidValue"]

    #noinspection PyShadowingBuiltins
    def __init__(self, title, url, type="folder"):
        """ Creates a new MediaItem.

        The `url` can contain an url to a site more info about the item can be
        retrieved, for instance for a video item to retrieve the media url, or
        in case of a folder where child items can be retrieved.

        Essential is that no encoding (like UTF8) is specified in the title of
        the item. This is all taken care of when creating Kodi items in the
        different methods.

        :param str|unicode title:   The title of the item, used for appearance in lists.
        :param str|unicode url:     Url that used for further information retrieval.
        :param str type:            Type of MediaItem (folder, video, audio). Defaults to 'folder'.

        """

        name = title.strip()

        self.name = name
        self.url = url
        self.actionUrl = None
        self.MediaItemParts = []
        self.description = ""
        self.thumb = ""                           # : The local or remote image for the thumbnail of episode
        self.fanart = ""                          # : The fanart url
        self.icon = ""                            # : low quality icon for list

        self.__date = ""                          # : value show in interface
        self.__timestamp = datetime.datetime.min  # : value for sorting, this one is set to minimum so if non is set, it's shown at the bottom

        self.type = type                          # : video, audio, folder, append, page, playlist
        self.dontGroup = False                    # : if set to True this item will not be auto grouped.
        self.isLive = False                       # : if set to True, the item will have a random QuerySting param
        self.isGeoLocked = False                  # : if set to True, the item is GeoLocked to the channels language (o)
        self.isDrmProtected = False               # : if set to True, the item is DRM protected and cannot be played (^)
        self.isPaid = False                       # : if set to True, the item is a Paid item and cannot be played (*)
        self.__infoLabels = dict()                # : Additional Kodi InfoLabels

        self.complete = False
        self.downloaded = False
        self.downloadable = False
        self.items = []
        self.HttpHeaders = dict()                 # : http headers for the item data retrieval
        self.rating = None

        # Items that are not essential for pickled
        self.isCloaked = False
        self.metaData = dict()                    # : Additional data that is for internal / routing use only

        # GUID used for identifcation of the object. Do not set from script, MD5 needed
        # to prevent UTF8 issues
        try:
            self.guid = "%s%s" % (EncodingHelper.encode_md5(title), EncodingHelper.encode_md5(url or ""))
        except:
            Logger.error("Error setting GUID for title:'%s' and url:'%s'. Falling back to UUID", title, url, exc_info=True)
            self.guid = self.__get_uuid()
        self.guidValue = int("0x%s" % (self.guid,), 0)

    def append_single_stream(self, url, bitrate=0, subtitle=None):
        """ Appends a single stream to a new MediaPart of this MediaItem.

        This methods creates a new MediaPart item and adds the provided
        stream to its MediaStreams collection. The newly created MediaPart
        is then added to the MediaItem's MediaParts collection.

        :param str url:         Url of the stream.
        :param int bitrate:     Bitrate of the stream (default = 0).
        :param str subtitle:    Url of the subtitle of the mediapart.

        :return: A reference to the created MediaPart.
        :rtype: MediaItemPart

        """

        new_part = MediaItemPart(self.name, url, bitrate, subtitle)
        self.MediaItemParts.append(new_part)
        return new_part

    def create_new_empty_media_part(self):
        """ Adds an empty MediaPart to the MediaItem.

        This method is used to create an empty MediaPart that can be used to
        add new stream to. The newly created MediaPart is appended to the
        MediaItem.MediaParts list.

        :return: The new MediaPart object (as a reference) that was appended.
        :rtype: MediaItemPart

        """

        new_part = MediaItemPart(self.name)
        self.MediaItemParts.append(new_part)
        return new_part

    def has_media_item_parts(self):
        """ Return True if there are any MediaItemParts present with streams for
        this MediaItem

        :return: True if there are any MediaItemParts present with streams for
                 this MediaItem
        :rtype: bool

        """

        for part in self.MediaItemParts:
            if len(part.MediaStreams) > 0:
                return True

        return False

    def is_playable(self):
        """ Returns True if the item can be played in a Media Player.

        At this moment it returns True for:
        * type = 'video'
        * type = 'audio'

        :return: Returns true if this is a playable MediaItem
        :rtype: bool

        """

        return self.type.lower() in ('video', 'audio', 'playlist')

    def is_resolvable(self):
        """Returns True if the item can be played directly stream (using setResolveUrl).

        At this moment it returns True for:
        * type = 'video'
        * type = 'audio'

        :return: True if the MediaItem's URL can be resolved by setResolved().
        :rtype: bool

        """

        return self.type.lower() in ('video', 'audio')

    def has_track(self):
        """ Does this MediaItem have a TrackNumber InfoLabel

        :return: if the track was set.
        :rtype: bool
        """

        return MediaItem.LabelTrackNumber in self.__infoLabels

    def has_date(self):
        """ Returns if a date was set

        :return: True if a date was set.
        :rtype: bool

        """

        return self.__timestamp > datetime.datetime.min

    def clear_date(self):
        """ Resets the date (used for favourites for example). """

        self.__timestamp = datetime.datetime.min
        self.__date = ""

    def set_info_label(self, label, value):
        """ Set a Kodi InfoLabel and its value.

        See http://kodi.wiki/view/InfoLabels
        :param str label: the name of the label
        :param Any value: the value to assign

        """

        self.__infoLabels[label] = value

    def set_season_info(self, season, episode):
        """ Set season and episode information

        :param str|int season:  The Season Number
        :param str|int episode: The Episode Number

        """

        if season is None or episode is None:
            Logger.warning("Cannot set EpisodeInfo without season and episode")
            return

        self.__infoLabels["Episode"] = int(episode)
        self.__infoLabels["Season"] = int(season)
        return

    def set_date(self, year, month, day,
                 hour=None, minutes=None, seconds=None, only_if_newer=False, text=None):
        """ Sets the datetime of the MediaItem.

        Sets the datetime of the MediaItem in the self.__date and the
        corresponding text representation of that datetime.

        `hour`, `minutes` and `seconds` can be optional and will be set to 0 in
        that case. They must all be set or none of them. Not just one or two of
        them.

        If `only_if_newer` is set to True, the update will only occur if the set
        datetime is newer then the currently set datetime.

        The text representation can be overwritten by setting the `text` keyword
        to a specific value. In that case the timestamp is set to the given time
        values but the text representation will be overwritten.

        If the values form an invalid datetime value, the datetime value will be
        reset to their default values.

        :param int|str year:        The year of the datetime.
        :param int|str month:       The month of the datetime.
        :param int|str day:         The day of the datetime.
        :param int|str hour:        The hour of the datetime (Optional)
        :param int|str minutes:     The minutes of the datetime (Optional)
        :param int|str seconds:     The seconds of the datetime (Optional)
        :param bool only_if_newer:  Update only if the new date is more recent then the
                                    currently set one
        :param str text:            If set it will overwrite the text in the date label the
                                    datetime is also set.

        :return: The datetime that was set.
        :rtype: datetime.datetime

        """

        # date_format = xbmc.getRegion('dateshort')
        # correct a small bug in Kodi
        # date_format = date_format[1:].replace("D-M-", "%D-%M")
        # dateFormatLong = xbmc.getRegion('datelong')
        # timeFormat = xbmc.getRegion('time')
        # date_time_format = "%s %s" % (date_format, timeFormat)

        try:
            date_format = "%Y-%m-%d"     # "%x"
            date_time_format = date_format + " %H:%M"

            if hour is None and minutes is None and seconds is None:
                time_stamp = datetime.datetime(int(year), int(month), int(day))
                date = time_stamp.strftime(date_format)
            else:
                time_stamp = datetime.datetime(int(year), int(month), int(day), int(hour), int(minutes), int(seconds))
                date = time_stamp.strftime(date_time_format)

            if only_if_newer and self.__timestamp > time_stamp:
                return

            self.__timestamp = time_stamp
            if text is None:
                self.__date = date
            else:
                self.__date = text

        except ValueError:
            Logger.error("Error setting date: Year=%s, Month=%s, Day=%s, Hour=%s, Minutes=%s, Seconds=%s", year, month, day, hour, minutes, seconds, exc_info=True)
            self.__timestamp = datetime.datetime.min
            self.__date = ""

        return self.__timestamp

    def get_kodi_item(self, name=None):
        """Creates a Kodi item with the same data is the MediaItem.

        This item is used for displaying purposes only and changes to it will
        not be passed on to the MediaItem.

        :param str name:    Overwrites the name of the Kodi item.

        :return: a complete Kodi ListItem
        :rtype: xbmcgui.ListItem

        """

        # Update name and descriptions
        name_post_fix, description_post_fix = self.__update_title_and_description_with_limitations()

        name = self.__get_title(name)
        name = "%s%s" % (name, name_post_fix)
        name = self.__full_decode_text(name)

        if self.description is None:
            self.description = ''

        description = "%s%s" % (self.description.lstrip(), description_post_fix)
        description = self.__full_decode_text(description)
        if description is None:
            description = ""

        # the Kodi ListItem date
        # date: string (%d.%m.%Y / 01.01.2009) - file date
        if self.__timestamp > datetime.datetime.min:
            kodi_date = self.__timestamp.strftime("%d.%m.%Y")
            kodi_year = self.__timestamp.year
        else:
            kodi_date = ""
            kodi_year = 0

        # Get all the info labels starting with the ones set and then add the specific ones
        info_labels = self.__infoLabels.copy()
        info_labels["Title"] = name
        if kodi_date:
            info_labels["Date"] = kodi_date
            info_labels["Year"] = kodi_year
        if self.type != "audio":
            info_labels["Plot"] = description

        # now create the Kodi item
        item = xbmcgui.ListItem(name or "<unknown>", self.__date)
        item.setLabel(name)
        item.setLabel2(self.__date)

        # set a flag to indicate it is a item that can be used with setResolveUrl.
        if self.is_resolvable():
            Logger.trace("Setting IsPlayable to True")
            item.setProperty("IsPlayable", "true")

        # specific items
        Logger.trace("Setting InfoLabels: %s", info_labels)
        if self.type == "audio":
            item.setInfo(type="music", infoLabels=info_labels)
        else:
            item.setInfo(type="video", infoLabels=info_labels)

        try:
            item.setIconImage(self.icon)
        except:
            # it was deprecated
            pass

        # now set all the art to prevent duplicate calls to Kodi
        if self.fanart and not AddonSettings.hide_fanart():
            item.setArt({'thumb': self.thumb, 'icon': self.icon, 'fanart': self.fanart})
        else:
            item.setArt({'thumb': self.thumb, 'icon': self.icon})

        # Set Artwork
        # art = dict()
        # for l in ("thumb", "poster", "banner", "fanart", "clearart", "clearlogo", "landscape"):
        #     art[l] = self.thumb
        # item.setArt(art)

        # We never set the content resolving, Retrospect does this. And if we do, then the custom
        # headers are removed from the URL when opening the resolved URL.
        try:
            item.setContentLookup(False)
        except:
            # apparently not yet supported on this Kodi version3
            pass
        return item

    def get_kodi_play_list(self, bitrate, update_item_urls=False, proxy=None):
        """ Creates a Kodi Playlist containing the MediaItemParts in this MediaItem

        Keyword Arguments:
        bitrate        : integer         - The bitrate of the streams that should be in
                                           the playlist. Given in kbps

        updateItemUrls : [opt] boolean   - If specified, the Playlist items will
                                           have a path pointing to the actual stream
        proxy          : [opt] ProxyInfo - The proxy to set

        Returns:
        a Kodi Playlist for this MediaItem

        If the Bitrate keyword is omitted the the bitrate is retrieved using the
        default bitrate settings:

        """

        play_list = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        srt = None

        play_list_items = []
        if not update_item_urls:
            # if we are not using the resolveUrl method, we need to clear the playlist and set the index
            play_list.clear()
            current_index = 0
        else:
            # copy into a list so we can add stuff in between (we can't do that in an
            # Kodi PlayList) and then create a new playlist item
            current_index = play_list.getposition()  # this is the location at which we are now.
            if current_index < 0:
                # no items where there, so we can just start at position 0
                current_index = 0

            Logger.info("Updating the playlist for item at position %s and trying to preserve other playlist items", current_index)
            for i in range(0, len(play_list)):
                Logger.trace("Copying play_list item %s out of %s", i + 1, len(play_list))
                play_list_items.append((play_list[i].getfilename(), play_list[i]))

            start_list = reduce(lambda x, y: "%s\n%s" % (x, y[0]), play_list_items, "Starting with Playlist Items (%s)" % (len(play_list_items),))
            Logger.debug(start_list)
            play_list.clear()

        log_text = "Creating playlist for Bitrate: %s kbps\n%s\nSelected Streams:\n" % (bitrate, self)

        # for each MediaItemPart get the URL, starting at the current index
        index = current_index
        for part in self.MediaItemParts:
            if len(part.MediaStreams) == 0:
                Logger.warning("Ignoring empty MediaPart: %s", part)
                continue

            # get the playlist item
            (stream, kodi_item) = part.get_kodi_play_list_item(self, bitrate, update_item_urls=update_item_urls)

            stream_url = stream.Url
            kodi_params = dict()

            # set proxy information if present
            self.__set_kodi_proxy_info(kodi_item, stream, stream_url, kodi_params, log_text, proxy)

            # Now add the actual HTTP headers
            for k in part.HttpHeaders:
                kodi_params[k] = HtmlEntityHelper.url_encode(part.HttpHeaders[k])

            if kodi_params:
                kodi_query_string = reduce(lambda x, y: "%s&%s=%s" %
                                                        (x, y, kodi_params[y]), kodi_params.keys(), "").lstrip("&")
                Logger.debug("Adding Kodi Stream parameters: %s\n%s", kodi_params, kodi_query_string)
                stream_url = "%s|%s" % (stream.Url, kodi_query_string)

            if index == current_index and index < len(play_list_items):
                # We need to replace the current item.
                Logger.trace("Replacing current Kodi ListItem at Playlist index %s (of %s)", index, len(play_list_items))
                play_list_items[index] = (stream_url, kodi_item)
            else:
                # We need to add at the current index
                Logger.trace("Inserting Kodi ListItem at Playlist index %s", index)
                play_list_items.insert(index, (stream_url, kodi_item))

            index += 1

            # for now we just add the last subtitle, this will not work if each
            # part has it's own subtitles.
            srt = part.Subtitle

        Logger.info(log_text)

        end_list = reduce(lambda x, y: "%s\n%s" % (x, y[0]), play_list_items, "Ended with Playlist Items (%s)" % (len(play_list_items),))
        Logger.debug(end_list)
        for play_list_item in play_list_items:
            play_list.add(play_list_item[0], play_list_item[1])

        return play_list, srt

    def __set_kodi_proxy_info(self, kodi_item, stream, stream_url, kodi_params, log_text, proxy):
        """ Updates a Kodi ListItem with the correct Proxy configuration taken from the ProxyInfo
        object.

        :param xbmcgui.ListItem kodi_item:  The current Kodi ListItem.
        :param MediaStream stream:          The current Stream object.
        :param str stream_url:              The current Url for the Stream object (might have
                                            been changed in the mean time by other calls)
        :param dict[str,str] kodi_params:   A dictionary of Kodi Parameters.
        :param str log_text:                The current text that will be logged.
        :param ProxyInfo proxy:             The ProxyInfo object

        :return: The new log text
        :rtype: str

        """
        if not proxy:
            return log_text

        log_text = "%s\n + %s" % (log_text, stream)

        if stream.Downloaded:
            log_text = "%s\n    + Not adding proxy as the stream is already downloaded" % (log_text,)
        elif proxy.Scheme.startswith("http") and not stream.Url.startswith("http"):
            log_text = "%s\n    + Not adding proxy due to scheme mismatch" % (log_text,)
        elif proxy.Scheme == "dns":
            log_text = "%s\n    + Not adding DNS proxy for Kodi streams" % (log_text,)
        elif not proxy.use_proxy_for_url(stream_url):
            log_text = "%s\n    + Not adding proxy due to filter mismatch" % (log_text,)
        else:
            if AddonSettings.is_min_version(17):
                # See ffmpeg proxy in https://github.com/xbmc/xbmc/commit/60b21973060488febfdc562a415e11cb23eb9764
                kodi_item.setProperty("proxy.host", proxy.Proxy)
                kodi_item.setProperty("proxy.port", str(proxy.Port))
                kodi_item.setProperty("proxy.type", proxy.Scheme)
                if proxy.Username:
                    kodi_item.setProperty("proxy.user", proxy.Username)
                if proxy.Password:
                    kodi_item.setProperty("proxy.password", proxy.Password)
                log_text = "%s\n    + Adding (Krypton) %s" % (log_text, proxy)
            else:
                kodi_params["HttpProxy"] = proxy.get_proxy_address()
                log_text = "%s\n    + Adding (Pre-Krypton) %s" % (log_text, proxy)
        return log_text

    def __get_uuid(self):
        """ Generates a Unique Identifier based on Time and Random Integers """

        t = long(time.time() * 1000)
        r = long(random.random() * 100000000000000000L)
        a = random.random() * 100000000000000000L
        data = str(t) + ' ' + str(r) + ' ' + str(a)
        data = EncodingHelper.encode_md5(data)
        return data

    def __full_decode_text(self, string_value):
        """ Decodes a byte encoded string with HTML content into Unicode String

        Arguments:
        stringValue : string - The byte encoded string to decode

        Returns:
        An Unicode String with all HTML entities replaced by their UTF8 characters

        The decoding is done by first decode the string to UTF8 and then replace
        the HTML entities to their UTF8 characters.

        """

        if string_value is None:
            return None

        if string_value == "":
            return ""

        # then get rid of the HTML entities
        string_value = HtmlEntityHelper.convert_html_entities(string_value)
        return string_value

    def __str__(self):
        """ String representation 

        :return: The String representation
        :rtype: str

        """

        value = self.name

        if self.is_playable():
            if len(self.MediaItemParts) > 0:
                value = "MediaItem: %s [Type=%s, Complete=%s, IsLive=%s, Date=%s, Downloadable=%s, Geo/DRM=%s/%s]" % \
                        (value, self.type, self.complete, self.isLive, self.__date,
                         self.downloadable, self.isGeoLocked, self.isDrmProtected)
                for media_part in self.MediaItemParts:
                    value = "%s\n%s" % (value, media_part)
                value = "%s" % (value,)
            else:
                value = "%s [Type=%s, Complete=%s, unknown urls, IsLive=%s, Date=%s, Downloadable=%s, Geo/DRM=%s/%s]" \
                        % (value, self.type, self.complete, self.isLive, self.__date,
                           self.downloadable, self.isGeoLocked, self.isDrmProtected)
        else:
            value = "%s [Type=%s, Url=%s, Date=%s, IsLive=%s, Geo/DRM=%s/%s]" \
                    % (value, self.type, self.url, self.__date, self.isLive, self.isGeoLocked, self.isDrmProtected)

        return value

    def __eq__(self, item):
        """ checks 2 items for Equality

        Arguments:
        item : MediaItem - The item to check for equality.

        Returns:
        the output of self.__equals(item).

        """
        return self.__equals(item)

    def __ne__(self, item):
        """ returns NOT Equal

        Arguments:
        item : MediaItem - The item to check for equality.

        Returns:
        the output of not self.__equals(item).

        """

        return not self.__equals(item)

    def __hash__(self):
        """ returns the hash value """

        return hash(self.guidValue)

    def __equals(self, other):
        """ Checks two MediaItems for equality

        :param MediaItem other: The other item.

        :return: whether the objects are equal (if the item's GUID's match).
        :rtype: bool

        """

        if not other:
            return False

        # if self.name == item.name and self.guid != item.guid:
        #    Logger.Debug("Duplicate names, but different guid: %s (%s), %s (%s)", self.name, self.url, item.name, item.url)
        return self.guidValue == other.guidValue

    def __update_title_and_description_with_limitations(self):
        """ Updates the title/name and description with the symbols for DRM, GEO and Paid.

        :return:            (tuple) name postfix, description postfix
        :rtype: tuple[str,str]

        """

        geo_lock = "&ordm;"  # º
        drm_lock = "^"       # ^
        paid = "&ordf;"     # ª
        cloaked = "&uml;"   # ¨
        description_addition = []
        title_postfix = []

        description = ""
        title = ""

        if self.isDrmProtected:
            title_postfix.append(drm_lock)
            description_addition.append(
                LanguageHelper.get_localized_string(LanguageHelper.DrmProtected))

        if self.isGeoLocked:
            title_postfix.append(geo_lock)
            description_addition.append(
                LanguageHelper.get_localized_string(LanguageHelper.GeoLockedId))

        if self.isPaid:
            title_postfix.append(paid)
            description_addition.append(
                LanguageHelper.get_localized_string(LanguageHelper.PremiumPaid))

        if self.isCloaked:
            title_postfix.append(cloaked)
            description_addition.append(
                LanguageHelper.get_localized_string(LanguageHelper.HiddenItem))

        # actually update it
        if description_addition:
            description_addition = ", ".join(description_addition)
            description = "\n\n%s" % (description_addition, )
        if title_postfix:
            title = " %s" % ("".join(title_postfix), )

        return title, description

    def __get_title(self, name):
        """ Create the title based on the MediaItems name and type.

        :param str name: the name to update.

        :return: an updated name
        :rtype: str

        """

        if not name:
            name = self.name

        if self.type == 'page':
            # We need to add the Page prefix to the item
            name = "%s %s" % (LanguageHelper.get_localized_string(LanguageHelper.Page), name)
            Logger.debug("MediaItem.__get_title :: Adding Page Prefix")

        elif self.__date != '' and not self.is_playable():
            # not playable items should always show date
            name = "%s (%s)" % (name, self.__date)

        folder_prefix = AddonSettings.get_folder_prefix()
        if self.type == "folder" and not folder_prefix == "":
            name = "%s %s" % (folder_prefix, name)

        return name

    def __setstate__(self, state):
        """ Sets the current MediaItem's state based on the pickled value. However, it also adds
        newly added class variables so old items won't brake.

        @param state: a default Pickle __dict__
        """

        # creating a new MediaItem here should not cause too much performance issues, as not very many
        # will be depickled.

        m = MediaItem("", "")
        self.__dict__ = m.__dict__
        self.__dict__.update(state)

    # We are not using the __getstate__ for now
    # def __getstate__(self):
    #     return self.__dict__


class MediaItemPart:
    """Class that represents a MediaItemPart"""

    def __init__(self, name, url="", bitrate=0, subtitle=None, *args):
        """ Creates a MediaItemPart with <name> with at least one MediaStream
        instantiated with the values <url> and <bitrate>.
        The MediaPart could also have a <subtitle> or Properties in the <*args>

        If a subtitles was provided, the subtitle will be downloaded and stored
        in the XOT cache. When played, the subtitle is shown. Due to the Kodi
        limitation only one subtitle can be set on a playlist, this will be
        the subtitle of the first MediaPartItem

        :param str name:                    The name of the MediaItemPart.
        :param str url:                     The URL of the stream of the MediaItemPart.
        :param int bitrate:                 The bitrate of the stream of the MediaItemPart.
        :param str|None subtitle:           The url of the subtitle of this MediaItemPart
        :param tuple[str,str] args:         A list of arguments that will be set as properties
                                            when getting an Kodi Playlist Item

        """

        Logger.trace("Creating MediaItemPart '%s' for '%s'", name, url)
        self.Name = name
        self.MediaStreams = []
        self.Subtitle = ""
        self.CanStream = True
        self.HttpHeaders = dict()                   # :  HTTP Headers for stream playback

        # set a subtitle
        if subtitle is not None:
            self.Subtitle = subtitle

        if not url == "":
            # set the stream that was passed
            self.append_media_stream(url, bitrate)

        # set properties
        self.Properties = []
        for prop in args:
            self.add_property(prop[0], prop[1])
        return

    def append_media_stream(self, url, bitrate, *args):
        """Appends a mediastream item to the current MediaPart

        The bitrate could be set to None.

        :param url:                     The url of the MediaStream.
        :param int|str bitrate:         The bitrate of the MediaStream.
        :param tuple[str,str] args:     A list of arguments that will be set as properties
                                        when getting an Kodi Playlist Item

        :return: The newly added MediaStream by reference.
        :rtype: MediaStream

        """

        stream = MediaStream(url, bitrate, *args)
        self.MediaStreams.append(stream)
        return stream

    def add_property(self, name, value):
        """ Adds a property to the MediaPart.

        Appends a new property to the self.Properties dictionary. On playback
        these properties will be set to the Kodi PlaylistItem as properties.

        :param str name:    The name of the property.
        :param str value:   The value of the property.

        """

        Logger.debug("Adding property: %s = %s", name, value)
        self.Properties.append((name, value))

    def get_kodi_play_list_item(self, parent, bitrate, update_item_urls=False):
        """ Returns a Kodi List Item than can be played or added to an Kodi
        PlayList.

        Returns a tuple with (stream url, Kodi PlayListItem). The Kodi PlayListItem
        can be used to add to a Kodi Playlist. The stream url can be used
        to set as the stream for the PlayListItem using xbmc.PlayList.add()

        If quality is not specified the quality is retrieved from the add-on
        settings.

        :param MediaItem parent:        The parent MediaItem.
        :param int bitrate:             The bitrate for the list items
        :param bool update_item_urls:   If set, the Kodi items will have a path
                                        that corresponds with the actual stream.

        :return: A tuple with (stream url, Kodi PlayListItem).
        :rtype: tuple[MediaStream,ListItem]

        """

        if self.Name:
            Logger.debug("Creating Kodi ListItem '%s'", self.Name)
            item = parent.get_kodi_item(name=self.Name)
        else:
            Logger.debug("Creating Kodi ListItem '%s'", parent.name)
            item = parent.get_kodi_item()

        if not bitrate:
            raise ValueError("Bitrate not specified")

        for prop in self.Properties:
            Logger.trace("Adding property: %s", prop)
            item.setProperty(prop[0], prop[1])

        # now find the correct quality stream and set the properties if there are any
        stream = self.get_media_stream_for_bitrate(bitrate)
        if stream.Adaptive:
            Adaptive.set_max_bitrate(stream, max_bit_rate=bitrate)

        for prop in stream.Properties:
            Logger.trace("Adding Kodi property: %s", prop)
            item.setProperty(prop[0], prop[1])

        if update_item_urls:
            Logger.info("Updating Kodi playlist-item path: %s", stream.Url)
            item.setProperty("path", stream.Url)

        return stream, item

    def get_media_stream_for_bitrate(self, bitrate):
        """Returns the MediaStream for the requested bitrate.

        Arguments:
        bitrate : integer - The bitrate of the stream in kbps

        Returns:
        The url of the stream with the requested bitrate.

        If bitrate is not specified the highest bitrate stream will be used.

        """

        # order the items by bitrate
        self.MediaStreams.sort()
        best_stream = None
        best_distance = None

        for stream in self.MediaStreams:
            if stream.Bitrate is None:
                # no bitrate set, see if others are available
                continue

            # this is the bitrate-as-max-limit-method
            if stream.Bitrate > bitrate:
                # if the bitrate is higher, continue for more
                continue
            # if commented ^^ , we get the closest-match-method

            # determine the distance till the bitrate
            distance = abs(bitrate - stream.Bitrate)

            if best_distance is None or best_distance > distance:
                # this stream is better, so store it.
                best_distance = distance
                best_stream = stream

        if best_stream is None:
            # no match, take the lowest bitrate
            return self.MediaStreams[0]

        return best_stream

    def __cmp__(self, other):
        """ Compares 2 items based on their appearance order:

        * -1 : If the item is lower than the current one
        *  0 : If the item is order is equal
        *  1 : If the item is higher than the current one

        The comparison is done base on the Name only.

        :param MediaItemPart other:     The other part to compare to
        :return: The comparison result.
        :rtype: int

        """

        if other is None:
            return -1

        # compare names
        return cmp(self.Name, other.Name)

    def __eq__(self, other):
        """ Checks 2 items for Equality. Equality takes into consideration:

        * Name
        * Subtitle
        * Length of the MediaStreams
        * Compares all the MediaStreams in the slef.MediaStreams

         :param MediaItemPart other: The part the test for equality.

         :return: Returns true if the items are equal.
         :rtype: bool

        """

        if other is None:
            return False

        if not other.Name == self.Name:
            return False

        if not other.Subtitle == self.Subtitle:
            return False

        # now check the strea
        if not len(self.MediaStreams) == len(other.MediaStreams):
            return False

        for i in range(0, len(self.MediaStreams)):
            if not self.MediaStreams[i] == other.MediaStreams[i]:
                return False

        # if we reach this point they are equal.
        return True

    def __str__(self):
        """ String representation for the MediaPart

        :return: The String representation
        :rtype: str

        """

        text = "MediaPart: %s [CanStream=%s, HttpHeaders=%s]" % (self.Name, self.CanStream, self.HttpHeaders)

        if self.Subtitle != "":
            text = "%s\n + Subtitle: %s" % (text, self.Subtitle)

        for prop in self.Properties:
            text = "%s\n + Property: %s=%s" % (text, prop[0], prop[1])

        for stream in self.MediaStreams:
            text = "%s\n + %s" % (text, stream)
        return text


class MediaStream:
    """Class that represents a Mediastream with <url> and a specific <bitrate>"""

    def __init__(self, url, bitrate=0, *args):
        """Initialises a new MediaStream

        :param str url:                 The URL of the stream.
        :param int|str bitrate:         The bitrate of the stream (defaults to 0).
        :param tuple[str,str] args:     (name, value) for any stream property.

        """

        Logger.trace("Creating MediaStream '%s' with bitrate '%s'", url, bitrate)
        self.Url = url
        self.Bitrate = int(bitrate)
        self.Downloaded = False
        self.Properties = []
        self.Adaptive = False

        for prop in args:
            self.add_property(prop[0], prop[1])
        return

    def add_property(self, name, value):
        """ Appends a new property to the self.Properties dictionary. On playback
        these properties will be set to the Kodi PlaylistItem as properties.

        Example:    
        strm.add_property("inputstreamaddon", "inputstream.adaptive")
        strm.add_property("inputstream.adaptive.manifest_type", "mpd")

        :param str name:    The name of the property.
        :param str value:   The value of the property.

        """

        Logger.debug("Adding stream property: %s = %s", name, value)
        self.Properties.append((name, value))

    def __cmp__(self, other):
        """ Compares 2 items based on their bitrate:

        * -1 : If the item is lower than the current one
        *  0 : If the item is order is equal
        *  1 : If the item is higher than the current one

        The comparison is done base on the bitrate only.

        :param MediaStream other:     The other part to compare to

        :return: The comparison result.
        :rtype: int

        """

        if other is None:
            return -1

        return cmp(self.Bitrate, other.Bitrate)

    def __eq__(self, other):
        """ Checks 2 items for Equality

        Equality takes into consideration:

        * The url of the MediaStream

        :param MediaStream other:   The stream to check for equality.

        :return: True if the items are equal.
        :rtype: bool

        """

        # also check for URL
        if other is None:
            return False

        return self.Url == other.Url

    def __str__(self):
        """ String representation

        :return: The String representation
        :rtype: str

        """

        text = "MediaStream: %s [bitrate=%s, downloaded=%s]" % (self.Url, self.Bitrate, self.Downloaded)
        for prop in self.Properties:
            text = "%s\n    + Property: %s=%s" % (text, prop[0], prop[1])

        return text
