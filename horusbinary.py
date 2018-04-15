#!/usr/bin/env python
#
#   Project Horus Binary/RTTY Telemetry - Habitat/OziMux Uploader
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   This code accepts the following telemetry formats via stdin:
#       - Horus Binary Telemetry packets, as hexadecimal data, followed by a newline.
#       - RTTY Telemetry ($$<data>*<checksum>\n)
#   Packets are parsed and added to a queue for upload to the Habitat database.
#   OziMux telemetry messages are also emitted on UDP port 55683
#
#   Dependencies:
#       The following Python packages are required (install with: sudo pip install <package>)
#       * crcmod
#       * requests
#
#   Example Usage (SSB demod via GQRX, decoding using 'horus_api' from codec2-dev):
#   $ nc -l -u localhost 7355 | ./horus_demod <arguments> | python horusbinary.py --usercall=MYCALL 
#
import argparse
import crcmod
import datetime
import json
import logging
import os
import Queue
import requests
import socket
import struct
import sys
import time
from threading import Thread
from base64 import b64encode
from hashlib import sha256


# Global variables, instantiated in main()
habitat_uploader = None

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
                inhibit = False):
        ''' Create a Habitat Uploader object. ''' 

        self.user_callsign = user_callsign
        self.upload_timeout = upload_timeout
        self.queue_size = queue_size
        self.habitat_upload_queue = Queue.Queue(queue_size)
        self.inhibit = inhibit

        # Start the uploader thread.
        self.habitat_uploader_running = True
        self.uploadthread = Thread(target=self.habitat_upload_thread)
        self.uploadthread.start()

    def habitat_upload(self, sentence):
        ''' Upload a UKHAS-standard telemetry sentence to Habitat '''

        # Generate payload to be uploaded
        _sentence_b64 = b64encode(sentence)
        _date = datetime.datetime.utcnow().isoformat("T") + "Z"
        _user_call = self.user_callsign

        _data = {
            "type": "payload_telemetry",
            "data": {
                "_raw": _sentence_b64
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

        # Run the request.
        _req = requests.put(_url, data=json.dumps(_data), timeout=self.upload_timeout)

        if _req.status_code == 201:
            logging.info("Uploaded sentence to Habitat successfully")
        elif _req.status_code == 403:
            logging.info("Sentence uploaded to Habitat, but already present in database.")
        else:
            logging.error("Error uploading to Habitat. Status Code: %d" % _req.status_code)

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
        except Queue.Full:
            logging.error("Upload Queue is full, sentence discarded.")
        except Exception as e:
            logging.error("Error adding sentence to queue: %s" % str(e))


    def close(self):
        ''' Shutdown uploader thread. '''
        self.habitat_uploader_running = False


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

def oziplotter_upload_basic_telemetry(time, latitude, longitude, altitude, udp_port=55683):
    """
    Send a sentence of position data to Oziplotter/OziMux, via UDP.
    """
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
        _ozisock.sendto(sentence,('<broadcast>',udp_port))
        _ozisock.close()
        logging.debug("Send Telemetry to OziMux (%d): %s" % (udp_port, sentence.strip()))
        return sentence
    except Exception as e:
        logging.error("Failed to send OziMux packet: %s" % str(e))


def ozimux_upload(sentence, udp_port=55683):
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
        _calc_crc = crc16_ccitt(_telem)

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
        oziplotter_upload_basic_telemetry(_time, _latitude, _longitude, _altitude, udp_port=udp_port)
        return

    except Exception as e:
        logging.error("Could not parse ASCII Sentence - %s" % str(e))
        return



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
def decode_horus_binary(data, payload_call = 'HORUSBINARY'):
    ''' Decode a string containing a horus binary packet, and produce a UKHAS ASCII string '''

    horus_format_struct = "<BHBBBffHBBbBH"
    # Attempt to unpack the input data into a struct.
    try:
        unpacked = struct.unpack(horus_format_struct, data)
    except Exception as e:
        logging.error("Error parsing binary telemetry - %s" % str(e))
        return None


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
        return None

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
    _checksum = crc16_ccitt(_sentence[2:])
    _output = _sentence + "*" + _checksum + "\n"

    logging.info("Decoded Binary Telemetry as: %s" % _output.strip())

    return _output



def handle_ukhas(data):
    ''' Handle a line of UKHAS-standard ASCII Telemetry '''
    global habitat_uploader

    logging.info("ASCII Sentence: %s" % data)

    # Emit OziMux telemetry
    ozimux_upload(data)

    # Upload data via Habitat
    if habitat_uploader is not None:
        habitat_uploader.add(data)
    else:
        logging.error("Habitat Uploader has not been initialized.")

    return


def handle_binary(data, payload_call = 'HORUSBINARY'):
    '''  Handle a line of binary telemetry, provided as hexadecimal. '''
    global habitat_uploader
    logging.info("Hexadecimal Sentence: %s" % data)

    # Attempt to parse the line of data as hexadecimal.
    try:
        _binary_string = data.decode('hex')
    except TypeError as e:
        logging.error("Error parsing line as hexadecimal (%s): %s" % (str(e), data))
        return

    # Attempt to decode the line as binary telemetry.
    _decoded_sentence = decode_horus_binary(_binary_string, payload_call)

    # If the decode succeeds, upload it
    if _decoded_sentence is not None:
        # Emit OziMux telemetry
        ozimux_upload(_decoded_sentence)

        # Upload data via Habitat
        if habitat_uploader is not None:
            habitat_uploader.add(_decoded_sentence)
        else:
            logging.error("Habitat Uploader has not been initialized.")





def main():
    ''' Main Function '''
    global habitat_uploader
    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

    # Read command-line arguments
    parser = argparse.ArgumentParser(description="Project Horus Binary/RTTY Telemetry Handler", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--mycall", type=str, default='HORUS_RX', help="Habitat Uploader Callsign, i.e. N0CALL")
    parser.add_argument("--payloadcall", type=str, default='HORUSBINARY', help="Payload Callsign, when converting binary telemetry to ASCII")
    parser.add_argument("--noupload", action="store_true", default=False, help="Disable Habitat upload.")
    args = parser.parse_args()


    # Start the Habitat uploader thread.
    habitat_uploader = HabitatUploader(user_callsign = args.mycall, inhibit=args.noupload)


    # Main loop
    try:
        while True:
            # Read lines in from stdin, and strip off any trailing newlines
            data = sys.stdin.readline()

            if data == '':
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
                handle_binary(data, args.payloadcall)

    except KeyboardInterrupt:
        logging.info("Caught CTRL-C, exiting.")

    habitat_uploader.close()

    return


if __name__ == '__main__':
    main()
