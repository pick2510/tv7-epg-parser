import json
import os.path
import argparse
from lxml import etree
import dateutil.parser
import requests
import time
import gzip

BASE_URL = "https://tv7api2.tv.init7.net/api/"
DATE_FORMAT = '%Y%m%d%H%M%S%z'
MAX_DOWNLOADS = 10
MAX_FILE_AGE = 20*60*60
TMP_FOLDER = "/home/strebdom/git/tv7-epg-parser/tmp/"
WEB_ROOT="/var/www/html/"
arg_parser = argparse.ArgumentParser(
    description='fetch epg data from init7 and return it')
arg_parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable Debugging')
args = vars(arg_parser.parse_args())


def addChannels(root_elem, channels_data):
    for result in channels_data:
        channel = etree.Element("channel")
        channel.set('id',  result['canonical_name'])
        name_elem = etree.SubElement(channel, "display-name")
        name_elem.text = result['name']
        ordernum_elem = etree.SubElement(channel, "display-name")
        ordernum_elem.text = str(result['ordernum'])  

        icon_elem = etree.SubElement(channel, "icon")
        icon_elem.set('src', result['logo'])
        root.append(channel)


def addProgrammes(root_elem, programme_data):
    for result in programme_data:
        programme = etree.Element("programme")
        for key, value in result.items():
            if key == 'pk':
                continue
            elif key == 'timeslot':
                startTime = dateutil.parser.isoparse(value['lower'])
                stopTime = dateutil.parser.isoparse(value['upper'])
                programme.set("start", startTime.strftime(DATE_FORMAT))
                programme.set("stop", stopTime.strftime(DATE_FORMAT))
                continue
            elif key == 'channel':
                programme.set("channel",value['canonical_name'])
                lang = etree.SubElement(programme, "language")
                lang.text = value['language']
                programme.append(lang)
                continue
            elif key == 'title':
                title_elem = etree.SubElement(programme, "title")
                title_elem.set("lang", result['channel']['language'])
                title_elem.text = value
                continue
            elif key == 'sub_title':
                sub_title_elem = etree.SubElement(programme, "sub-title")
                sub_title_elem.set("lang", result['channel']['language'])
                sub_title_elem.text = value
            elif key == 'desc':
                desc_elem = etree.SubElement(programme, "desc")
                desc_elem.set("lang", result['channel']['language'])
                desc_elem.text = value
            elif key == 'categories' and value:
                for category_str in value:
                    category_elem = etree.SubElement(programme, "category")
                    category_elem.set("lang", result['channel']['language'])
                    category_elem.text = category_str
            elif key == 'country' and value:
                country_elem = etree.SubElement(programme, "country")
                country_elem.set("lang", result['channel']['language'])
                country_elem.text = value
            elif key == 'date' and value:
                date_elem = etree.SubElement(programme, "date")
                date_elem.text = str(value)
            elif key == 'icons' and value:
                for icon_url in value:
                    category_elem = etree.SubElement(programme, "icon")
                    category_elem.set("src", icon_url)
            elif key == 'credits' and value:
                credits_elem = etree.SubElement(programme, "credits")
                for credit in value:
                    credit_elem = etree.SubElement(
                        credits_elem, credit['position'])
                    credit_elem.text = credit['name']
            elif key == 'rating_system' and value:
                rating_elem = programme.find('rating')
                if rating_elem is None:
                    rating_elem = etree.SubElement(programme, 'rating')
                rating_elem.set("system", value)
            elif key == 'rating' and value:
                rating_elem = programme.find('rating')
                if rating_elem is None:
                    rating_elem = etree.SubElement(programme, 'rating')
                rating_elem.text = value
            elif key == 'episode_num_system' and value:
                episode_num_elem = programme.find('episode-num')
                if episode_num_elem is None:
                    episode_num_elem = etree.SubElement(
                        programme, 'episode-num')
                episode_num_elem.set("system", value)
            elif key == 'episode_num' and value:
                episode_num_elem = programme.find('episode-num')
                if episode_num_elem is None:
                    episode_num_elem = etree.SubElement(
                        programme, 'episode-num')
                episode_num_elem.text = value
            elif key == 'premiere' and value:
                premiere_elem = etree.SubElement(programme, 'premiere')
                if not isinstance(value, (bool)):
                    premiere_elem.text = value
            elif key == 'subtitles' and value:
                subtitles_elem = etree.SubElement(programme, 'subtitles')
                if not isinstance(value, (bool)):
                    subtitles_elem.text = value
            elif key == 'star_rating' and value:
                star_rating_elem = etree.SubElement(programme, 'star-rating')
                star_rating_elem.text = value
        root_elem.append(programme)


def _file_age_in_seconds(pathname):
    return time.time() - os.path.getmtime(pathname)


def is_valid_json(myjson):
  try:
    json_object = json.loads(myjson)
  except ValueError as e:
    return False
  return True

downloadCount = 0


def _downloadFile(filename, url):
    global downloadCount
    if not os.path.isfile(filename) or (downloadCount < MAX_DOWNLOADS and _file_age_in_seconds(filename) > MAX_FILE_AGE):
        if args['debug']:
            print("downloading ", url)
        r = requests.get(url, allow_redirects=True)
        if(is_valid_json(r.content)):
            open(filename, 'wb').write(r.content)
        time.sleep(1)
        downloadCount = downloadCount+1
    else:
        if args['debug']:
            print("skipping ", url)

# @GET("allowed/")
# Call<AllowedResponse> allowed();
# curl "${BASE_URL}allowed/" > allowed.json
# TODO: Check allowed URL


######
# start building xmltv file
######

# @GET("tvchannel/")
# Call<TvChannelListResponse> tvChannelList();
# curl "${BASE_URL}tvchannel/" > tvChannelList.json
url = BASE_URL+"tvchannel/"
filename = os.path.join(TMP_FOLDER, 'tvChannelList' + ".json")
_downloadFile(filename, url)
root = etree.Element("tv")
with open(filename) as json_file:
    channels_data = json.load(json_file)
    addChannels(root, channels_data['results'])

    for channel in channels_data['results']:
        channel_id = channel['pk']

        # @GET("epg/")
        # Call<EPGListResponse> getEPG(@Query("channel") String paramString);
        # curl "${BASE_URL}epg/?channel=4c8a7d39-009d-4835-b6f9-69c7268fd9d4" > getEPG-channel.json
        url = BASE_URL+"epg/?channel="+channel_id+"&limit=999"

        filename = os.path.join(
            TMP_FOLDER, 'getEPG-'+channel_id + ".json")
        _downloadFile(filename, url)

        with open(filename) as json_file:

            try:
                programme_data = json.load(json_file)

                if 'results' in programme_data:
                    addProgrammes(root, programme_data['results'])
                else:
                    if args['debug']:
                        print(programme_data)
            except json.JSONDecodeError as e:
                if args['debug']:
                    print(filename + ": ")
                    print(e)
 
    doctype = '<!DOCTYPE tv SYSTEM "https://github.com/XMLTV/xmltv/raw/master/xmltv.dtd">'
    document_str = etree.tostring(
        root, pretty_print=False, xml_declaration=True, encoding="UTF-8", doctype=doctype)

    xmltv_file = os.path.join(WEB_ROOT, 'tv7' + ".xml.gz")
    with gzip.open(xmltv_file, 'wb') as f:
        f.write(document_str)
