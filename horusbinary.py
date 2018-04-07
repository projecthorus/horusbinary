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
#   $ nc -l -u localhost 7355 | ./horus_api <arguments> | python horusbinary.py --usercall=MYCALL 
#
import argparse
import crcmod
import datetime
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
                upload_timeout = 10):
        ''' Create a Habitat Uploader object. ''' 

        self.user_callsign = user_callsign
        self.upload_timeout = upload_timeout
        self.queue_size = queue_size
        self.habitat_upload_queue = Queue.Queue(queue_size)

        # Start the uploader thread.
        self.habitat_uploader_running = True
        self.uploadthread = Thread(target=self.habitat_upload_thread)
        self.uploadthread.start()

    def habitat_upload(self, sentence):
        ''' Upload a UKHAS-standard telemetry sentence to Habitat '''
        # TODO
        logging.info("Uploaded sentence to Habitat successfully")
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

        # Check the line has a '$$' header, and a trailing newline.
        # If not, add them.
        if sentence.startswith('$$') == False:
            sentence = '$$' + sentence

        if sentence[-1] is not '\n':
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
def decode_horus_binary(data):
    ''' Decode a string containing a horus binary packet, and produce a UKHAS ASCII string '''
    
    # TODO

    return None



def handle_ukhas(data):
    ''' Handle a line of UKHAS-standard ASCII Telemetry '''
    global habitat_uploader

    logging.debug("ASCII Sentence: %s" % data)

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
    logging.debug("Hexadecimal Sentence: %s" % data)

    # Attempt to parse the line of data as hexadecimal.
    try:
        _binary_string = data.decode('hex')
    except TypeError as e:
        logging.error("Error parsing line as hexadecimal (%s): %s" % (str(e), data))
        return

    # Attempt to decode the line as binary telemetry.
    _decoded_sentence = decode_horus_binary(_binary_string)

    # If the decode succeeds, upload it
    if _decoded_sentence is not None:
        # Emit OziMux telemetry
        ozimux_upload(_decoded_sentence)

        # Upload data via Habitat
        if habitat_uploader is not None:
            habitat_uploader.add(data)
        else:
            logging.error("Habitat Uploader has not been initialized.")





def main():
    ''' Main Function '''
    global habitat_uploader
    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

    # Read command-line arguments
    parser = argparse.ArgumentParser(description="Project Horus Binary/RTTY Telemetry Handler", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("usercall", type=str, help="Habitat Uploader Callsign, i.e. N0CALL")
    parser.add_argument("--payloadcall", type=str, default='HORUSBINARY', help="Payload Callsign, when converting binary telemetry to ASCII")
    args = parser.parse_args()


    # Start the Habitat uploader thread.
    habitat_uploader = HabitatUploader(user_callsign = args.usercall)


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