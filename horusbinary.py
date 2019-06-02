#!/usr/bin/env python
#
#   Project Horus Binary/RTTY Telemetry - Habitat/ChaseMapper Uploader
#
#   Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   This code accepts the following telemetry formats via stdin:
#       - Horus Binary Telemetry packets, as hexadecimal data, followed by a newline.
#       - RTTY Telemetry ($$$$$<data>*<checksum>\n)
#   Packets are parsed and added to a queue for upload to the Habitat database.
#   OziMux telemetry messages are also emitted on UDP port 55683, and 'Horus UDP'
#   messages on UDP port 55672.
#
#   Dependencies:
#       The following Python packages are required (install with: sudo pip install <package>)
#       * crcmod
#       * requests
#
#   Example Usage (SSB demod via GQRX, decoding using 'horus_api' from codec2-dev):
#   $ nc -l -u localhost 7355 | ./horus_demod <arguments> | python horusbinary.py
#
import argparse
import codecs
import crcmod
import datetime
import json
import logging
import os
import pprint
import random
import requests
import socket
import struct
import sys
import time
import traceback
from threading import Thread
from base64 import b64encode
from hashlib import sha256

try:
    # Python 2
    from Queue import Queue
except ImportError:
    # Python 3
    from queue import Queue

try:
    # Python 2
    from ConfigParser import RawConfigParser
except ImportError:
    # Python 3
    from configparser import RawConfigParser


# Global variables, instantiated in main()
habitat_uploader = None

# OziMux Telemetry output port
ozi_port = 55683

# Payload Summary Output Port
summary_port = -1

# Log file object
log_file = None
#
# Habitat Uploader Class
#

class HabitatUploader(object):
    ''' 
    Queued Habitat Telemetry Uploader class 
    
    Packets to be uploaded to Habitat are added to a queue for uploading.
    If an upload attempt times out, the packet is discarded.
    If the queue fills up (probably indicating no network connection, and a fast packet downlink rate),
    it is immediately emptied, to avoid upload of out-of-date packets.
    '''


    def __init__(self, user_callsign='FSK_DEMOD', 
                queue_size=16,
                upload_timeout = 10,
                upload_retries = 5,
                upload_retry_interval = 0.25,
                inhibit = False,
                ):
        ''' Create a Habitat Uploader object. ''' 

        self.user_callsign = user_callsign
        self.upload_timeout = upload_timeout
        self.upload_retries = upload_retries
        self.upload_retry_interval = upload_retry_interval
        self.queue_size = queue_size
        self.habitat_upload_queue = Queue(queue_size)
        self.inhibit = inhibit

        # Start the uploader thread.
        self.habitat_uploader_running = True
        self.uploadthread = Thread(target=self.habitat_upload_thread)
        self.uploadthread.start()

    def habitat_upload(self, sentence):
        ''' Upload a UKHAS-standard telemetry sentence to Habitat '''

        # Generate payload to be uploaded
        # b64encode accepts and returns bytes objects.
        _sentence_b64 = b64encode(sentence.encode('ascii'))
        _date = datetime.datetime.utcnow().isoformat("T") + "Z"
        _user_call = self.user_callsign

        _data = {
            "type": "payload_telemetry",
            "data": {
                "_raw": _sentence_b64.decode('ascii') # Convert back to a string to be serialisable
                },
            "receivers": {
                _user_call: {
                    "time_created": _date,
                    "time_uploaded": _date,
                    },
                },
        }

        # The URl to upload to.
        _url = "http://habitat.habhub.org/habitat/_design/payload_telemetry/_update/add_listener/%s" % sha256(_sentence_b64).hexdigest()

        # Delay for a random amount of time between 0 and upload_retry_interval*2 seconds.
        time.sleep(random.random()*self.upload_retry_interval*2.0)

        _retries = 0

        # When uploading, we have three possible outcomes:
        # - Can't connect. No point re-trying in this situation.
        # - The packet is uploaded successfult (201 / 403)
        # - There is a upload conflict on the Habitat DB end (409). We can retry and it might work.
        while _retries < self.upload_retries:
            # Run the request.
            try:
                _req = requests.put(_url, data=json.dumps(_data), timeout=self.upload_timeout)
            except Exception as e:
                logging.error("Habitat - Upload Failed: %s" % str(e))
                break

            if _req.status_code == 201 or _req.status_code == 403:
                # 201 = Success, 403 = Success, sentence has already seen by others.
                logging.info("Habitat - Uploaded sentence to Habitat successfully")
                _upload_success = True
                break
            elif _req.status_code == 409:
                # 409 = Upload conflict (server busy). Sleep for a moment, then retry.
                logging.info("Habitat - Upload conflict.. retrying.")
                time.sleep(random.random()*self.upload_retry_interval)
                _retries += 1
            else:
                logging.error("Habitat - Error uploading to Habitat. Status Code: %d." % _req.status_code)
                break

        if _retries == self.upload_retries:
            logging.error("Habitat - Upload conflict not resolved with %d retries." % self.upload_retries)

        return


    def habitat_upload_thread(self):
        ''' Handle uploading of packets to Habitat '''

        logging.info("Started Habitat Uploader Thread.")

        while self.habitat_uploader_running:

            if self.habitat_upload_queue.qsize() > 0:
                # If the queue is completely full, jump to the most recent telemetry sentence.
                if self.habitat_upload_queue.qsize() == self.queue_size:
                    while not self.habitat_upload_queue.empty():
                        sentence = self.habitat_upload_queue.get()

                    logging.warning("Habitat uploader queue was full - possible connectivity issue.")
                else:
                    # Otherwise, get the first item in the queue.
                    sentence = self.habitat_upload_queue.get()

                # Attempt to upload it.
                self.habitat_upload(sentence)

            else:
                # Wait for a short time before checking the queue again.
                time.sleep(0.1)

        logging.info("Stopped Habitat Uploader Thread.")


    def add(self, sentence):
        ''' Add a sentence to the upload queue '''

        if self.inhibit:
            # We have upload inhibited. Return.
            return

        # Handling of arbitrary numbers of $$'s at the start of a sentence:
        # Extract the data part of the sentence (i.e. everything after the $$'s')
        sentence = sentence.split('$')[-1]
        # Now add the *correct* number of $$s back on.
        sentence = '$$' +sentence

        if not (sentence[-1] == '\n'):
            sentence += '\n'

        try:
            self.habitat_upload_queue.put_nowait(sentence)
        except Exception as e:
            logging.error("Error adding sentence to queue: %s" % str(e))


    def close(self):
        ''' Shutdown uploader thread. '''
        self.habitat_uploader_running = False

#
# Habitat Listener Position
#

callsign_init = False
HABITAT_URL = "http://habitat.habhub.org/"
url_habitat_uuids = HABITAT_URL + "_uuids?count=%d"
url_habitat_db = HABITAT_URL + "habitat/"

uuids = []

def ISOStringNow():
    return "%sZ" % datetime.datetime.utcnow().isoformat()


def postListenerData(doc, timeout=10):
    global uuids, url_habitat_db
    # do we have at least one uuid, if not go get more
    if len(uuids) < 1:
        fetchUuids()

    # Attempt to add UUID and time data to document.
    try:
        doc['_id'] = uuids.pop()
    except IndexError:
        logging.error("Habitat - Unable to post listener data - no UUIDs available.")
        return False

    doc['time_uploaded'] = ISOStringNow()

    try:
        _r = requests.post(url_habitat_db, json=doc, timeout=timeout)
        return True
    except Exception as e:
        logging.error("Habitat - Could not post listener data - %s" % str(e))
        return False


def fetchUuids(timeout=10):
    global uuids, url_habitat_uuids

    _retries = 5

    while _retries > 0:
        try:
            _r = requests.get(url_habitat_uuids % 10, timeout=timeout)
            uuids.extend(_r.json()['uuids'])
            logging.debug("Habitat - Got UUIDs")
            return
        except Exception as e:
            logging.error("Habitat - Unable to fetch UUIDs, retrying in 10 seconds - %s" % str(e))
            time.sleep(10)
            _retries = _retries - 1
            continue

    logging.error("Habitat - Gave up trying to get UUIDs.")
    return


def initListenerCallsign(callsign, radio='', antenna=''):
    doc = {
            'type': 'listener_information',
            'time_created' : ISOStringNow(),
            'data': {
                'callsign': callsign,
                'antenna': antenna,
                'radio': radio,
                }
            }

    resp = postListenerData(doc)

    if resp is True:
        logging.debug("Habitat - Listener Callsign Initialized.")
        return True
    else:
        logging.error("Habitat - Unable to initialize callsign.")
        return False


def uploadListenerPosition(callsign, lat, lon, radio='', antenna=''):
    """ Initializer Listener Callsign, and upload Listener Position """

    # Attempt to initialize the listeners callsign
    resp = initListenerCallsign(callsign, radio=radio, antenna=antenna)
    # If this fails, it means we can't contact the Habitat server,
    # so there is no point continuing.
    if resp is False:
        return False

    doc = {
        'type': 'listener_telemetry',
        'time_created': ISOStringNow(),
        'data': {
            'callsign': callsign,
            'chase': False,
            'latitude': lat,
            'longitude': lon,
            'altitude': 0,
            'speed': 0,
        }
    }

    # post position to habitat
    resp = postListenerData(doc)
    if resp is True:
        logging.info("Habitat - Listener information uploaded.")
        return True
    else:
        logging.error("Habitat - Unable to upload listener information.")
        return False

#
# Utility functions
#

def crc16_ccitt(data):
    """
    Calculate the CRC16 CCITT checksum of *data*.
    
    (CRC16 CCITT: start 0xFFFF, poly 0x1021)
    """
    crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
    return hex(crc16(data))[2:].upper().zfill(4)



#
# OziMux UDP Packet Generation Functions
#

def oziplotter_upload_basic_telemetry(time, latitude, longitude, altitude):
    """
    Send a sentence of position data to Oziplotter/OziMux, via UDP.
    """
    global ozi_port
    sentence = "TELEMETRY,%s,%.5f,%.5f,%d\n" % (time, latitude, longitude, altitude)

    try:
        _ozisock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

        # Set up socket for broadcast, and allow re-use of the address
        _ozisock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        _ozisock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT doesn't work on all platforms, so catch the exception if it fails
        try:
            _ozisock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass
        # Send!
        try:
            _ozisock.sendto(sentence.encode('ascii'),('<broadcast>',ozi_port))
        except socket.error as e:
            logging.warning("Send to broadcast address failed, sending to localhost instead.")
            _ozisock.sendto(sentence.encode('ascii'),('127.0.0.1',ozi_port))

        _ozisock.close()
        logging.debug("Sent Telemetry to OziMux (%d): %s" % (ozi_port, sentence.strip()))
        return sentence
    except Exception as e:
        logging.error("Failed to send OziMux packet: %s" % str(e))


def ozimux_upload(sentence):
    ''' Attempt to parse a supplied sentence and emit it as a OziMux-compatible UDP sentence '''

    # Try and proceed through the following. If anything fails, we have a corrupt sentence.
    try:
        # Strip out any leading/trailing whitespace.
        _sentence = sentence.strip()

        # First, try and find the start of the sentence, which always starts with '$$''
        _sentence = _sentence.split('$$')[-1]
        # Hack to handle odd numbers of $$'s at the start of a sentence
        if _sentence[0] == '$':
            _sentence = _sentence[1:]
        # Now try and split out the telemetry from the CRC16.
        _telem = _sentence.split('*')[0]
        _crc = _sentence.split('*')[1]

        # Now check if the CRC matches.
        _calc_crc = crc16_ccitt(_telem.encode('ascii'))

        if _calc_crc != _crc:
            logging.error("Could not parse ASCII Sentence - CRC Fail.")
            return

        # We now have a valid sentence! Extract fields..
        _fields = _telem.split(',')

        _time = _fields[2]
        _latitude = float(_fields[3])
        _longitude = float(_fields[4])
        _altitude = int(_fields[5])
        # The rest we don't care about.

        # Perform some sanity checks on the data.

        # Attempt to parse the time string. This will throw an error if any values are invalid.
        try:
            _time_dt = datetime.datetime.strptime(_time, "%H:%M:%S")
        except:
            logging.error("Could not parse ASCII Sentence - Invalid Time.")
            return

        # Check if the lat/long is 0.0,0.0 - no point passing this along.
        if _latitude == 0.0 or _longitude == 0.0:
            logging.error("Could not parse ASCII Sentence - Zero Lat/Long.")
            return

        # Place a limit on the altitude field. We generally store altitude on the payload as a uint16, so it shouldn't fall outside these values.
        if _altitude > 65535 or _altitude < 0:
            logging.error("Could not parse ASCII Sentence - Invalid Altitude.")
            return

        # We are now pretty sure we have valid data - upload the sentence.
        oziplotter_upload_basic_telemetry(_time, _latitude, _longitude, _altitude)
        return

    except Exception as e:
        logging.error("Could not parse ASCII Sentence - %s" % str(e))
        return


def send_payload_summary(telemetry):
    """ Send a payload summary message into the network via UDP broadcast.

    Args:
    telemetry (dict): Telemetry dictionary to send.
    port (int): UDP port to send to.

    """
    global summary_port

    # If the summary port is set to -1, then payload summary output has not been enabled.
    if summary_port == -1:
        return

    try:
        # Do a few checks before sending.
        if telemetry['latitude'] == 0.0 and telemetry['longitude'] == 0.0:
            logging.error("Horus UDP - Zero Latitude/Longitude, not sending.")
            return

        packet = {
            'type' : 'PAYLOAD_SUMMARY',
            'callsign' : telemetry['callsign'],
            'latitude' : telemetry['latitude'],
            'longitude' : telemetry['longitude'],
            'altitude' : telemetry['altitude'],
            'speed' : telemetry['speed'],
            'heading': -1,
            'time' : telemetry['time'],
            'comment' : 'Horus Binary',
            'temp': telemetry['temp'],
            'sats': telemetry['sats'],
            'batt_voltage': telemetry['batt_voltage']
        }

        # Set up our UDP socket
        _s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        _s.settimeout(1)
        # Set up socket for broadcast, and allow re-use of the address
        _s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Under OSX we also need to set SO_REUSEPORT to 1
        try:
            _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass

        try:
            _s.sendto(json.dumps(packet).encode('ascii'), ('<broadcast>',summary_port))
        # Catch any socket errors, that may occur when attempting to send to a broadcast address
        # when there is no network connected. In this case, re-try and send to localhost instead.
        except socket.error as e:
            logging.debug("Horus UDP - Send to broadcast address failed, sending to localhost instead.")
            _s.sendto(json.dumps(packet).encode('ascii'), ('127.0.0.1', summary_port))

        _s.close()

    except Exception as e:
        logging.error("Horus UDP - Error sending Payload Summary: %s" % str(e))


#
# Binary Packet Decoder
#

# Binary Packet Format:
# Refer https://github.com/darksidelemm/RS41HUP/blob/master/main.c#L72
# struct TBinaryPacket
# {
# uint8_t   PayloadID;
# uint16_t  Counter;
# uint8_t   Hours;
# uint8_t   Minutes;
# uint8_t   Seconds;
# float   Latitude;
# float   Longitude;
# uint16_t    Altitude;
# uint8_t   Speed; // Speed in Knots (1-255 knots)
# uint8_t   Sats;
# int8_t   Temp; // Twos Complement Temp value.
# uint8_t   BattVoltage; // 0 = 0v, 255 = 5.0V, linear steps in-between.
# uint16_t Checksum; // CRC16-CCITT Checksum.
# };
def decode_horus_binary(data, payload_list = {}):
    ''' Decode a string containing a horus binary packet, and produce a UKHAS ASCII string '''

    horus_format_struct = "<BHBBBffHBBbBH"
    # Attempt to unpack the input data into a struct.
    try:
        unpacked = struct.unpack(horus_format_struct, data)
    except Exception as e:
        logging.error("Error parsing binary telemetry - %s" % str(e))
        return (None, None)


    telemetry = {}
    telemetry['payload_id'] = unpacked[0]
    telemetry['counter'] = unpacked[1]
    telemetry['time'] = "%02d:%02d:%02d" % (unpacked[2],unpacked[3],unpacked[4])
    telemetry['latitude'] = unpacked[5]
    telemetry['longitude'] = unpacked[6]
    telemetry['altitude'] = unpacked[7]
    telemetry['speed'] = unpacked[8]
    telemetry['sats'] = unpacked[9]
    telemetry['temp'] = unpacked[10]
    telemetry['batt_voltage_raw'] = unpacked[11]
    telemetry['checksum'] = unpacked[12]

    # Validate the checksum.
    _crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
    _calculated_crc = _crc16(data[:-2])

    if _calculated_crc != telemetry['checksum']:
        logging.error("Checksum Mismatch - RX: %s, Calculated: %s" % (hex(telemetry['checksum']), hex(_calculated_crc)))
        return (None, None)

    # Determine the payload callsign
    if telemetry['payload_id'] not in payload_list:
        logging.error("Unknown Payload ID %d. Have you added your payload ID to payload_id_list.txt?" % telemetry['payload_id'])
        return (None, None)
    
    payload_call = payload_list[telemetry['payload_id']]

    telemetry['callsign'] = payload_call

    # Convert some of the fields into more useful units.
    telemetry['batt_voltage'] = 5.0*telemetry['batt_voltage_raw']/255.0

    # Generate the UKHAS ASCII sentence 
    _sentence = "$$%s,%d,%s,%.5f,%.5f,%d,%d,%d,%d,%.2f" % (
        payload_call,
        telemetry['counter'],
        telemetry['time'],
        telemetry['latitude'],
        telemetry['longitude'],
        telemetry['altitude'],
        telemetry['speed'],
        telemetry['sats'],
        telemetry['temp'],
        telemetry['batt_voltage'])
    # Append checksum
    _checksum = crc16_ccitt(_sentence[2:].encode('ascii'))
    _output = _sentence + "*" + _checksum + "\n"

    logging.info("Decoded Binary Telemetry as: %s" % _output.strip())

    return (_output, telemetry)



def handle_ukhas(data):
    ''' Handle a line of UKHAS-standard ASCII Telemetry '''
    global habitat_uploader

    logging.info("ASCII Sentence: %s" % data)

    # Emit OziMux telemetry
    ozimux_upload(data)

    # TODO - Send via payload summary message.

    # Upload data via Habitat
    if habitat_uploader is not None:
        habitat_uploader.add(data)
    else:
        logging.error("Habitat Uploader has not been initialized.")

    return


def handle_binary(data, payload_list = {}):
    '''  Handle a line of binary telemetry, provided as hexadecimal. '''
    global habitat_uploader, log_file
    logging.info("Hexadecimal Sentence: %s" % data)

    # Attempt to parse the line of data as hexadecimal.
    try:
        _binary_string = codecs.decode(data, 'hex')
    except TypeError as e:
        logging.error("Error parsing line as hexadecimal (%s): %s" % (str(e), data))
        return

    # Attempt to decode the line as binary telemetry.
    (_decoded_sentence, telem_dict) = decode_horus_binary(_binary_string, payload_list)

    # If the decode succeeds, upload it
    if _decoded_sentence is not None:
        # Emit OziMux telemetry
        ozimux_upload(_decoded_sentence)

        # Emit payload summary
        send_payload_summary(telem_dict)

        # Write out to the log tile
        if log_file != None:
            log_file.write(_decoded_sentence)
            log_file.flush()

        # Upload data via Habitat
        if habitat_uploader is not None:
            habitat_uploader.add(_decoded_sentence)
        else:
            logging.error("Habitat Uploader has not been initialized.")


def read_config(filename):
    ''' Read in the user configuation file.'''
    user_config = {
        'user_call' : 'HORUS_RX',
        'freedv_udp_port' : 55690,
        'ozi_udp_port' : 55683,
        'summary_port' : 55672,
        'station_lat' : 0.0,
        'station_lon' : 0.0,
        'radio_comment' : "",
        'antenna_comment' : ""
    }

    try:
        config = RawConfigParser()
        config.read(filename)

        user_config['user_call'] = config.get('user', 'callsign')
        user_config['station_lat'] = config.getfloat('user', 'station_lat')
        user_config['station_lon'] = config.getfloat('user', 'station_lon')
        user_config['radio_comment'] = config.get('user', 'radio_comment')
        user_config['antenna_comment'] = config.get('user', 'antenna_comment')
        user_config['freedv_udp_port'] = config.getint('freedv', 'udp_port')
        user_config['ozi_udp_port'] = config.getint('ozimux', 'ozimux_port')
        user_config['summary_port'] = config.getint('ozimux', 'summary_port')

        return user_config

    except:
        traceback.print_exc()
        logging.error("Could not parse config file, exiting. Have you copied user.cfg.example to user.cfg?")
        return None


def read_payload_list(filename="payload_id_list.txt"):
    """ Read in the payload ID list, and return the parsed data as a dictionary """

    # Dummy payload list.
    payload_list = {0:'4FSKTEST', 1:'HORUSBINARY'}

    try:
        with open(filename,'r') as file:
            for line in file:
                # Skip comment lines.
                if line[0] == '#':
                    continue
                else:
                    # Attempt to split the line with a comma.
                    _params = line.split(',')
                    if len(_params) != 2:
                        # Invalid line.
                        logging.error("Could not parse line: %s" % line)
                    else:
                        try:
                            _id = int(_params[0])
                            _callsign = _params[1].strip()
                            payload_list[_id] = _callsign
                        except:
                            logging.error("Error parsing line: %s" % line)
    except Exception as e:
        logging.error("Error reading Payload ID list, does it exist? - %s" % str(e))

    logging.info("Known Payload IDs:")
    for _payload in payload_list:
        logging.info("\t%s - %s" % (_payload, payload_list[_payload]))

    return payload_list


PAYLOAD_ID_LIST_URL = "https://raw.githubusercontent.com/projecthorus/horusbinary/master/payload_id_list.txt"

def grab_latest_payload_id_list(url, local_file="payload_id_list.txt"):
    """ Attempt to download the latest payload ID list from Github """

    # Download the list.
    try:
        logging.info("Attempting to download latest payload ID list from GitHub...")
        _r = requests.get(url, timeout=10)
    except Exception as e:
        logging.error("Unable to get latest payload ID list: %s" % str(e))
        return False

    # Check it is what we think it is..
    if "HORUS BINARY PAYLOAD ID LIST" not in _r.text:
        logging.error("Downloaded payload ID list is invalid.")
        return False

    # So now we most likely have a valid payload ID list, so write it out.
    with open(local_file, 'w') as f:
        f.write(_r.text)

    return True



def main():
    ''' Main Function '''
    global habitat_uploader, ozi_port, summary_port, log_file, payload_list

    # Read command-line arguments
    parser = argparse.ArgumentParser(description="Project Horus Binary/RTTY Telemetry Handler", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', type=str, default='user.cfg', help="Configuration file to use. Default: user.cfg")
    parser.add_argument("--noupload", action="store_true", default=False, help="Disable Habitat upload.")
    parser.add_argument("--stdin", action="store_true", default=False, help="Listen for data on stdin instead of via UDP.")
    parser.add_argument("--log", type=str, default="telemetry.log", help="Write decoded telemetry to this log file.")
    parser.add_argument("--debuglog", type=str, default="horusb_debug.log", help="Write debug log to this file.")
    parser.add_argument("--payload-list", type=str, default="payload_id_list.txt", help="List of known payload IDs.")
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Verbose output (set logging level to DEBUG)")
    args = parser.parse_args()

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', filename=args.debuglog, level=logging_level)
    stdout_format = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(stdout_format)
    logging.getLogger().addHandler(stdout_handler)

    # Read in the configuration file.
    user_config = read_config(args.config)

    if args.payload_list != "payload_id_list.txt":
        logging.info("Skipping update of payload ID list and using user-supplied file %s." % args.payload_list)
        payload_list = read_payload_list(args.payload_list)
    else:
        if grab_latest_payload_id_list(url=PAYLOAD_ID_LIST_URL):
            logging.info("Payload ID list updated successfuly.")
        else:
            logging.error("Could not update payload ID list, using local copy.")

        payload_list = read_payload_list("payload_id_list.txt")


    # If we could not read the configuration file, exit.
    if user_config == None:
        return
    else:
        logging.info("Using User Callsign: %s" % user_config['user_call'])

        if user_config['station_lat'] != 0.0:
            logging.info("Using Station Position: %.5f, %.5f" % (user_config['station_lat'], user_config['station_lon']))
            # Upload the listener position
            uploadListenerPosition(
                user_config['user_call'], 
                user_config['station_lat'],
                user_config['station_lon'],
                radio=user_config['radio_comment'],
                antenna=user_config['antenna_comment']
            )
        else:
            logging.info("No user position supplied, not uploading position to Habitat.")


    # Start the Habitat uploader thread.
    habitat_uploader = HabitatUploader(user_callsign = user_config['user_call'], inhibit=args.noupload)

    # Set OziMux output port
    ozi_port = user_config['ozi_udp_port']

    # Set Payload Summary port
    summary_port = user_config['summary_port']

    # Open the log file.
    log_file = open(args.log, 'a')

    if args.stdin == False:
        # Start up a UDP listener.
        s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.settimeout(1)
        # Set up the socket for address re-use.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # On BSD systems we have to do a bit extra.
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass
        s.bind(('127.0.0.1',user_config['freedv_udp_port']))
        logging.info("Opened UDP socket on port %d." % user_config['freedv_udp_port'])

    else:
        logging.info("Waiting for data on stdin.")


    logging.info("Started Horus Binary Uploader. Hit CTRL-C to exit.")
    # Main loop
    try:
        while True:
            # Read lines in from stdin, and strip off any trailing newlines
            if args.stdin == False:
                try:
                    data = s.recvfrom(1024)
                except socket.timeout:
                    data = None
                except KeyboardInterrupt:
                    break
                except:
                    traceback.print_exc()
                    data = None

                if data != None:
                    # s.recvfrom gives us bytes, convert to a string.
                    data = data[0].decode('ascii')
                else:
                    continue

            else:
                # This will give us a string in both Python 2 and 3.
                data = sys.stdin.readline()

            if (args.stdin == False) and (data == ''):
                # Empty line means stdin has been closed.
                logging.info("Caught EOF, exiting.")
                break

            # Otherwise, strip any newlines, and continue.
            data = data.rstrip()

            # If the line of data starts with '$$', we assume it is a UKHAS-standard ASCII telemetry sentence.
            # Otherwise, we assume it is a string of hexadecimal bytes, and attempt to parse it as a binary telemetry packet.
            if data.startswith('$$'):
                handle_ukhas(data)
            else:
                handle_binary(data, payload_list)

    except KeyboardInterrupt:
        logging.info("Caught CTRL-C, exiting.")

    habitat_uploader.close()
    log_file.close()

    return


if __name__ == '__main__':
    main()
