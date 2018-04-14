#!/usr/bin/env python
#
#   Fldigi Packet Counter Script
#
#   Used to test fldigi's RTTY demodulator performance.
#   The script connect to Fldigi's ARQ port, and listens for UKHAS-compliant sentences,
#   i.e. $$<packethere>*CRC16\n
#   You can either listen continuously, and then CTRL-C to exit and print the number of packets seen.
#   Usage: python fldigi_per.py --listen
#
#   Alternatively, you can specify a path to a set of wave files, which will be played through fldigi,
#   and the number of decodable packets in each file will be counted. You can also specify the expected number
#   of packets in the files (assumed to be the same for all input files)
#   Usage: python fldigi_per --files=/path/to/*.wav --expected=10
#
#   NOTE: You will need to modify the PLAY_CMD line below to reflect a command which will play wave files on your system.
#   In my case, i'm using sox to play a file into the 'SoundFlower' loopback audio device within OSX.
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#

import socket
import time
import glob
import sys
import os
import argparse
import Queue
import crcmod
import ConfigParser
from datetime import datetime
import traceback
from threading import Thread

# Command to play back a wave file. %s is replaced with the filename.
# This example uses sox to  play the wave-file into Soundflower (loopback audio under OSX)
#PLAY_CMD = "sox %s -t coreaudio \"Soundflower (2c\""
PLAY_CMD = "sox -r 8000 -b 16 -e signed-integer %s -t coreaudio \"Soundflower (2c\""
# Example for other platforms may be:
#PLAY_CMD = "play %s"


# fldigi ARQ port and hostname
FLDIGI_PORT = 7322
FLDIGI_HOST = '127.0.0.1'


class FldigiListener(object):
    """
    Attept to read UKHAS standard telemetry sentences from a local FlDigi instance, 
    and pass them onto a callback function.
    This is hacked together from FldigiBridge out of the horus_utils repo.
    """

    # Receive thread variables and buffers.
    rx_thread_running = True
    MAX_BUFFER_LEN = 256
    input_buffer = ""


    def __init__(self,
                fldigi_host = FLDIGI_HOST,
                fldigi_port = FLDIGI_PORT,
                log_file = "None",
                callback = None,
                valid_packet_callback = None
                ):

        self.fldigi_host = (fldigi_host, fldigi_port)
        self.callback = callback # Callback should accept a string, which is a valid sentence.
        self.valid_packet_callback = valid_packet_callback

        if log_file != "None":
            self.log_file = open(log_file,'a')
        else:
            self.log_file = None

        # Start receive thread.
        self.rx_thread_running = True
        self.t = Thread(target=self.rx_thread)
        self.t.start()


    def close(self):
        self.rx_thread_running = False

        if self.log_file is not None:
            self.log_file.close()


    def rx_thread(self):
        """
        Attempt to connect to fldigi and receive bytes.
        """
        while self.rx_thread_running:
            # Try and connect to fldigi. Keep looping until we have connected.
            try:
                _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _s.settimeout(1)
                _s.connect(self.fldigi_host)
            except socket.error as e:
                print("ERROR: Could not connect to fldigi - %s" % str(e))
                time.sleep(10)
                continue


            while self.rx_thread_running:
                try:
                    _char = _s.recv(1)
                except socket.timeout:
                    # No data received? Keep trying...
                    continue
                except Exception as e:
                    print("ERROR: Connection Issue - %s" % str(e))

                    try:
                        _s.close()
                    except:
                        pass
                    break

                # Append to input buffer.
                self.input_buffer += _char
                # Roll buffer if we've exceeded the max length.
                if len(self.input_buffer) > self.MAX_BUFFER_LEN:
                    self.input_buffer = self.input_buffer[1:]

                # If we have received a newline, attempt to process the current buffer of data.
                if _char == '\n':
                    self.process_data(self.input_buffer)
                    # Clear the buffer and continue.
                    self.input_buffer = ""
                else:
                    continue

        _s.close()


    def crc16_ccitt(self,data):
        """
        Calculate the CRC16 CCITT checksum of *data*.
        
        (CRC16 CCITT: start 0xFFFF, poly 0x1021)
        """
        crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
        return hex(crc16(data))[2:].upper().zfill(4)


    def send_to_callback(self, data):
            ''' If we have been given a callback, send data to it. '''
            if self.callback !=  None:
                try:
                    self.callback(data)
                except:
                    pass


    def process_data(self, data):
        """
        Attempt to process a line of data, and extract time, lat, lon and alt
        """
        try:
            # If we have a log file open, write the data out to disk.
            if self.log_file is not None:
                # Append trailing LF, since we don't get passed that.
                self.log_file.write(data)
                # Immediately flush the file to disk.
                self.log_file.flush()

            # Try and proceed through the following. If anything fails, we have a corrupt sentence.
            # Strip out any leading/trailing whitespace.
            data = data.strip()

            # First, try and find the start of the sentence, which always starts with '$$''
            _sentence = data.split('$$')[-1]
            # Hack to handle odd numbers of $$'s at the start of a sentence
            if _sentence[0] == '$':
                _sentence = _sentence[1:]
            # Now try and split out the telemetry from the CRC16.
            _telem = _sentence.split('*')[0]
            _crc = _sentence.split('*')[1]

            # Now check if the CRC matches.
            _calc_crc = self.crc16_ccitt(_telem)

            if _calc_crc != _crc:
                self.send_to_callback("CRC Fail.")
                return

            # We now have valid data! Send onto callback functions.

            if self.valid_packet_callback != None:
                try:
                    self.valid_packet_callback(_sentence)
                except:
                    pass

            if self.callback !=  None:
                try:
                    self.callback("VALID: " + _sentence)
                except:
                    pass

        except:
            return


def print_message(data):
    ''' Callback to print error messages from the Fldigi Listener '''
    print(data)


packet_count = 0

def valid_packet(data):
    ''' Callback to handle arrival of a valid packet '''
    global packet_count
    packet_count += 1



def play_file(filename):
    ''' Play a wave file '''
    play_cmd = PLAY_CMD % filename
    ret_code = os.system(play_cmd)

    return ret_code


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", action="store_true", default=False, help="Don't play wave files, just listen for packets until CTRL-C")
    parser.add_argument("--files", type=str, default="None", help="Path to wave files to play.")
    parser.add_argument("--expected", type=int, default=-1, help="Expected number of packets.")
    parser.add_argument("--log", type=str, default="None", help="Optional log file. All new telemetry data is appened to this file.")
    args = parser.parse_args()

    if args.files != "None":
        _file_list = glob.glob(args.files)

    _fldigi = FldigiListener(callback=print_message,
                    valid_packet_callback=valid_packet,
                    fldigi_host=FLDIGI_HOST,
                    fldigi_port=FLDIGI_PORT,
                    log_file=args.log)

    try:
        if args.listen:
            # Listen continuously
            while True:
                time.sleep(1)
        else:
            # Play a list of files.
            _out_str = ""
            for _file in _file_list:
                packet_count = 0

                play_file(_file)
                time.sleep(5)
                if args.expected == -1:
                    print("FILE %s: %d Packets" % (_file, packet_count))
                else:
                    _PER = float(packet_count)/float(args.expected)
                    _per_str = "FILE %s: %d/%d Packets, PER=%.3f" % (_file, packet_count, args.expected, _PER)
                    print(_per_str)
                    _out_str += _per_str + '\n'

            _fldigi.close()
            print(_out_str)

    except KeyboardInterrupt:
        _fldigi.close()
        print("Packet Count: %d" % packet_count)
        print("Caught CTRL-C, exiting.")

