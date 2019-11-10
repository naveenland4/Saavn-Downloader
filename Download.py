import ast
import base64
import html
import json
import os
import re
import urllib.request
import sys

import logger
import requests
import urllib3.request
from bs4 import BeautifulSoup
from mutagen.mp4 import MP4, MP4Cover
from pySmartDL import SmartDL
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from pyDes import *

# Pre Configurations
urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
unicode = str
raw_input = input

def getLibrary():
    url = "https://www.jiosaavn.com/api.php?__call=user.login&_marker=0"
    username = input("Enter your email for jiosaavn: ").strip()
    password = input("Enter your password for jiosaavn: ").strip()
    payload = { "username": username, "password": password }
    session = requests.Session()
    session.post(url, data=payload)
    response = session.get("https://www.jiosaavn.com/api.php?_format=json&__call=library.getAll")
    # library_json has ['song', 'show', 'artist', 'album', 'playlist', 'user'] as keys all of which have the id's as their value
    library_json = list(filter(lambda x: x.strip().startswith("{"), response.text.splitlines()))[0]
    library_json = json.loads(library_json)
    return library_json


def addtags(filename, json_data, playlist_name):
    audio = MP4(filename)
    audio['\xa9nam'] = html.unescape(unicode(json_data['song']))
    audio['\xa9ART'] = html.unescape(unicode(json_data['primary_artists']))
    audio['\xa9alb'] = html.unescape(unicode(json_data['album']))
    audio['aART'] = html.unescape(unicode(json_data['singers']))
    audio['\xa9wrt'] = html.unescape(unicode(json_data['music']))
    audio['desc'] = html.unescape(unicode(json_data['starring']))
    audio['\xa9gen'] = html.unescape(unicode(playlist_name))
    # audio['cprt'] = track['copyright'].encode('utf-8')
    # audio['disk'] = [(1, 1)]
    # audio['trkn'] = [(int(track['track']), int(track['maxtracks']))]
    audio['\xa9day'] = html.unescape(unicode(json_data['year']))
    audio['cprt'] = html.unescape(unicode(json_data['label']))
    # if track['explicit']:
    #    audio['rtng'] = [(str(4))]
    cover_url = json_data['image'][:-11] + '500x500.jpg'
    fd = urllib.request.urlopen(cover_url)
    cover = MP4Cover(fd.read(), getattr(MP4Cover, 'FORMAT_PNG' if cover_url.endswith('png') else 'FORMAT_JPEG'))
    fd.close()
    audio['covr'] = [cover]
    audio.save()


def setProxy():
    proxy_ip = ''
    if ('http_proxy' in os.environ):
        proxy_ip = os.environ['http_proxy']
    proxies = {
        'http': proxy_ip,
        'https': proxy_ip,
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0'
    }
    return proxies, headers


def setDecipher():
    return des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0", pad=None, padmode=PAD_PKCS5)


def searchSongs(query):
    songs_json = []
    albums_json = []
    playLists_json = []
    topQuery_json = []
    response = requests.get(
        'https://www.jiosaavn.com/api.php?_format=json&query={0}&__call=autocomplete.get'.format(query))
    if response.status_code == 200:
        response_json = json.loads(response.text.splitlines()[6])
        albums_json = response_json['albums']['data']
        songs_json = response_json['songs']['data']
        playLists_json = response_json['playlists']['data']
        topQuery_json = response_json['topquery']['data']
    return {"albums_json": albums_json,
            "songs_json": songs_json,
            "playLists_json": playLists_json,
            "topQuery_json": topQuery_json}


def getPlayList(listId):
    songs_json = []
    response = requests.get(
        'https://www.jiosaavn.com/api.php?listid={0}&_format=json&__call=playlist.getDetails'.format(listId), verify=False)
    if response.status_code == 200:
        # songs_json = list(filter(lambda x: x.strip().startswith("{"), response.text.splitlines()))[0]
        songs_json = [x for x in response.text.splitlines() if x.strip().startswith('{')][0]   # using list comprehension
        songs_json = json.loads(songs_json)
    return songs_json


def getAlbum(albumId):
   songs_json = []
   response = requests.get(
       'https://www.jiosaavn.com/api.php?_format=json&__call=content.getAlbumDetails&albumid={0}'.format(albumId),
       verify=False)
   if response.status_code == 200:
       # songs_json = list(filter(lambda x: x.strip().startswith("{"), response.text.splitlines()))[0]
       songs_json = [x for x in response.text.splitlines() if x.strip().startswith('{')][0]   # using list comprehension
       songs_json = json.loads(songs_json)
       print("Album name: ",songs_json["name"])
       album_name=songs_json["name"]
   return songs_json, album_name


def getShow(showId):
    show_homepage_json = []
    show_json = {}
    response = requests.get(
                'https://www.jiosaavn.com/api.php?_format=json&show_id={}&__call=show.getHomePage'.format(showId))
    # show_homepage_json = list(filter(lambda x: x.strip().startswith("{"), response.text.splitlines()))[0]
    show_homepage_json = [x for x in response.text.splitlines() if x.strip().startswith('{')][0]   # using list comprehension
    show_homepage_json = json.loads(show_homepage_json)
    no_of_seasons = len(show_homepage_json['seasons'])
    for season in range(no_of_seasons):   # Note that season value starts from 0 for the program but from 1 for the url
        no_of_episodes = show_homepage_json['seasons'][season]['more_info']['numEpisodes']
        response = requests.get(
            'https://www.jiosaavn.com/api.php?season_number={}&show_id={}&n={}&_format=json&__call=show.getAllEpisodes&sort_order=asc'.format(season+1, showId, no_of_episodes))
        # season_json = list(filter(lambda x: x.strip().startswith("["), response.text.splitlines()))[0]
        season_json = [x for x in response.text.splitlines() if x.strip().startswith('[')][0]   # using list comprehension
        season_json = json.loads(season_json)  # A list containing all the episodes in the season
        show_json[season] = season_json   # To build a dictionary containg all the season in the show
    return show_json


# This function doesn't work yet
def addtagsShow(filename, json_data):
    audio = MP4(filename)
    audio['\xa9nam'] = html.unescape(unicode(json_data['title']))
    try:
        audio['\xa9ART'] = ""
        for artist in json_data['more_info']['artistMap']['primary_artists']:
            audio['\xa9ART'] = audio['\xa9ART'] + ', ' + html.unescape(unicode(artist['name']))
    except:
        pass
    audio['\xa9alb'] = html.unescape(unicode(json_data['more_info']['show_title']))
    # audio['\xa9gen'] = html.unescape(unicode(playlist_name))
    audio['\xa9day'] = html.unescape(unicode(json_data['year']))
    audio['cprt'] = html.unescape(unicode(json_data['more_info']['label']))

    cover_url = json_data['image'][:-11] + '500x500.jpg'
    fd = urllib.request.urlopen(cover_url)
    cover = MP4Cover(fd.read(), getattr(MP4Cover, 'FORMAT_PNG' if cover_url.endswith('png') else 'FORMAT_JPEG'))
    fd.close()
    audio['covr'] = [cover]
    audio.save()


def downloadShow(show_json):
    album_name = show_json.get(0)[0]['more_info']['show_title']
    print("Show Name: {}".format(album_name))
    for season, season_json in show_json.items():
        season_name = 'Season {}'.format(season+1)
        print("Season: {}".format(season_name))
        des_cipher = setDecipher()
        for episode in season_json:
            try:
                enc_url = base64.b64decode(episode['more_info']['encrypted_media_url'].strip())
                dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode('utf-8')
                # dec_url = dec_url.replace('_96.mp4', '_320.mp4')   # Change in url gives invalid xml
                filename = html.unescape(episode['title']) + '.m4a'
                filename = filename.replace("\"", "'")
                filename = filename.replace(":", "-")
                filename = filename.replace("<", "-")
                filename = filename.replace(">", "-")
                filename = filename.replace("?", "-")
                filename = filename.replace("*", "-")
                filename = filename.replace("|", "-")
            except Exception as e:
                logger.error('Download Error' + str(e))
            try:
                location = os.path.join(os.path.sep, os.getcwd(), album_name, season_name, filename)
                if os.path.isfile(location):
                   print("Downloaded Show: {} - Season: {} - Episode: {}".format(album_name, season_name, filename))
                else :
                    print("Downloading Episode: {}".format(filename))
                    obj = SmartDL(dec_url, location)
                    obj.start()
                    # TODO: addtags will not work for shows
                    # addtagsShow(filename, episode)
                    # name = songs_json['name'] if ('name' in songs_json) else songs_json['listname']
                    # addtags(location, song, name)
                    print('\n')
            except Exception as e:
                 logger.error('Download Error' + str(e))


def downloadAllPlayList(library_json):
    playListIDs = library_json.get('playlist')
    if playListIDs is not None:
        print("Playlists found: {}".format(len(playListIDs)))
        for playList in playListIDs:
            playListID = playList['id']
            downloadSongs(getPlayList(playListID))


def downloadAllAlbums(library_json):
    albumIDs = library_json.get('album')
    if albumIDs is not None:
        print("Albums found: {}".format(len(albumIDs)))
        for albumId in albumIDs:
            try:
                json_data, album_nm=getAlbum(albumId)
                album_name = album_nm.replace("&quot;", "'")
                downloadSongs(json_data)
            except:
                print('Error getting album with ID: {}'.format(albumId))


def dowloadAllShows(library_json):
    if library_json.get('show') is not None:
        for showId in library_json['show']:
            # TODO download the show
            downloadShow(getShow(showId))


def getSong(songId):
    songs_json = []
    response = requests.get(
        'http://www.jiosaavn.com/api.php?songid={0}&_format=json&__call=song.getDetails'.format(songId), verify=False)
    if response.status_code == 200:
        print(response.text)
        songs_json = json.loads(response.text.splitlines()[5])
    return songs_json


def getHomePage():
    playlists_json = []
    response = requests.get(
        'https://www.jiosaavn.com/api.php?__call=playlist.getFeaturedPlaylists&_marker=false&language=tamil&offset=1&size=250&_format=json',
        verify=False)
    if response.status_code == 200:
        playlists_json = json.loads(response.text.splitlines()[2])
        playlists_json = playlists_json['featuredPlaylists']
    return playlists_json


def downloadSongs(songs_json):
    des_cipher = setDecipher()
    for song in songs_json['songs']:
        try:
            enc_url = base64.b64decode(song['encrypted_media_url'].strip())
            dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode('utf-8')
            dec_url = dec_url.replace('_96.mp4', '_320.mp4')
            filename = html.unescape(song['song']) + '.m4a'
            filename = filename.replace("\"", "'")
            filename = filename.replace(":", "-") 
            filename = filename.replace("<", "-") 
            filename = filename.replace(">", "-") 
            filename = filename.replace("?", "-") 
            filename = filename.replace("*", "-") 
            filename = filename.replace("|", "-")
        except Exception as e:
            logger.error('Download Error' + str(e))
        try:
            location = os.path.join(os.path.sep, os.getcwd(), album_name, filename)
            if os.path.isfile(location):
               print("Downloaded %s" % filename)
            else :
                print("Downloading %s" % filename)
                obj = SmartDL(dec_url, location)
                obj.start()
                name = songs_json['name'] if ('name' in songs_json) else songs_json['listname']
                addtags(location, song, name)
                print('\n')
        except Exception as e:
             logger.error('Download Error' + str(e))


if __name__ == '__main__':
    album_name="songs"

    if len(sys.argv) > 1 and sys.argv[1].lower() == "-p":
        downloadAllPlayList(getLibrary())
    elif len(sys.argv) > 1 and sys.argv[1].lower() == "-a":
        downloadAllAlbums(getLibrary())
    elif len(sys.argv) > 1 and sys.argv[1].lower() == '-s':
        dowloadAllShows(getLibrary())
    else:
        input_url = input('Enter the url: ').strip()
        try:
            proxies, headers = setProxy()
            res = requests.get(input_url, proxies=proxies, headers=headers)
        except Exception as e:
            logger.error('Error accessing website error: ' + e)

        soup = BeautifulSoup(res.text, "lxml")

        try:
            getPlayListID = soup.select(".flip-layout")[0]["data-listid"]
            if getPlayListID is not None:
                print("Initiating PlayList Downloading")
                downloadSongs(getPlayList(getPlayListID))
                sys.exit()
        except Exception as e:
            print('...')
        try:
            getAlbumID = soup.select(".play")[0]["onclick"]
            getAlbumID = ast.literal_eval(re.search("\[(.*?)\]", getAlbumID).group())[1]
            if getAlbumID is not None:
                print("Initiating Album Downloading")
                json_data, album_nm=getAlbum(getAlbumID)
                album_name = album_nm.replace("&quot;", "'")
                downloadSongs(json_data)
                
        except Exception as e:
            print('...')
            print("Please paste link of album or playlist")

# getSongID = soup.select(".current-song")[0]["data-songid"]
# if getSongID is not None:
#    print(getPlayListID)
#    sys.exit()
# for playlist in getHomePage():
#     print(playlist)
#     id = raw_input()
#     if id is "1":
#       downloadSongs(getPlayList(playlist['listid']))
# queryresults = searchSongs('nannare')
# print(json.dumps(getSong(queryresults['topQuery_json'][0]['id']), indent=2))
# response = requests.head(dec_url)
# if os.path.isfile(location) if (os.stat(location).st_size >  int(response.headers["Content-Length"])) else False:
