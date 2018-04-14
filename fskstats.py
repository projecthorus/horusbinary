#!/usr/bin/env python
#
#	fsk_demod Statistics GUI, v2.0
#	Accepts the stats output from fsk_demod on stdin, and plots it.
#
#	Mark Jessop 2018-04-15 <vk5qi@rfhead.net>
#
#	NOTE: This is intended to be run on a 'live' stream of samples, and hence expects
#	updates at about 10Hz. Anything faster will fill up the input queue and be discarded.
#
#	Call using: 
#	<producer>| ./fsk_demod 2X 8 923096 115387 - - S 2> >(python ~/Dev/codec2-dev/octave/fskdemodgui.py) | <consumer>
#
#
import argparse
import json
import Queue
import socket
import sys
import time
import traceback
from threading import Thread
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg

parser = argparse.ArgumentParser()
parser.add_argument("--udp", type=int, default=-1, help="Listen for data on a provided UDP port instead of stdin.")
parser.add_argument("--wide", action="store_true", default=False, help="Alternate wide arrangement of widgets, for placement at bottom of 4:3 screen.")
args = parser.parse_args()

# Some settings...
update_rate = 2 # Hz
history_size = 100 # 10 seconds at 10Hz...
history_scale = np.linspace((-1*history_size+1)/float(update_rate),0,history_size)

# Input queue
in_queue = Queue.Queue(1) # 1-element FIFO... 

win = pg.GraphicsWindow()
win.setWindowTitle('FSK Demodulator Modem Statistics')


# Plot objects
ebno_plot = win.addPlot(title="Eb/No")
ppm_plot = win.addPlot(title="Sample Clock Offset")
if args.wide == False:
	win.nextRow()
else:
	win.resize(1024,200)
fest_plot = pg.PlotItem() 
eye_plot = win.addPlot(title="Eye Diagram")
# Disable auto-ranging on eye plot and fix axes for a big speedup...
spec_plot = win.addPlot(title="Spectrum")
spec_plot.setYRange(0,40)
spec_plot.setLabel('left','SNR (dB)')
spec_plot.setLabel('bottom','FFT Bin')
# Configure plot labels and scales.
ebno_plot.setLabel('left','Eb/No (dB)')
ebno_plot.setLabel('bottom','Time (seconds)')
ebno_plot.setYRange(0,25)
ppm_plot.setLabel('left','Clock Offset (ppm)')
ppm_plot.setLabel('bottom','Time (seconds)')
fest_plot.setLabel('left','Frequency (Hz)')
fest_plot.setLabel('bottom','Time (seconds)')
eye_plot.disableAutoRange()
eye_plot.setYRange(0,1)
eye_plot.setXRange(0,15)
eye_xr = 15

# Data arrays...
ebno_data = np.zeros(history_size)*np.nan
ppm_data = np.zeros(history_size)*np.nan
fest_data = np.zeros((4,history_size))*np.nan

# Curve objects, so we can update them...
spec_curve = spec_plot.plot([0])
ebno_curve = ebno_plot.plot(x=history_scale,y=ebno_data)
ppm_curve = ppm_plot.plot(x=history_scale,y=ppm_data)
fest1_curve = fest_plot.plot(x=history_scale,y=fest_data[0,:],pen='r') # f1 = Red
fest2_curve = fest_plot.plot(x=history_scale,y=fest_data[1,:],pen='g') # f2 = Blue
fest3_curve = fest_plot.plot(x=history_scale,y=fest_data[2,:],pen='b') # f3 = Greem
fest4_curve = fest_plot.plot(x=history_scale,y=fest_data[3,:],pen='m') # f4 = Magenta

# Plot update function. Reads from queue, processes and updates plots.
def update_plots():
	global timeout,timeout_counter,eye_plot,ebno_curve, ppm_curve, fest1_curve, fest2_curve, ebno_data, ppm_data, fest_data, in_queue, eye_xr, spec_curve

	try:
		if in_queue.empty():
			return
		in_data_raw = in_queue.get_nowait()
		in_data = json.loads(in_data_raw)
	except Exception as e:

		sys.stderr.write(str(e))
		sys.stderr.write(in_data_raw)
		return

	# Roll data arrays
	ebno_data[:-1] = ebno_data[1:]
	ppm_data[:-1] = ppm_data[1:]
	fest_data = np.roll(fest_data,-1,axis=1)


	# Try reading in the new data points from the dictionary.
	try:
		new_ebno = in_data['EbNodB']
		new_ppm = in_data['ppm']
		new_fest1 = in_data['f1_est']
		new_fest2 = in_data['f2_est']
		new_spec = in_data['samp_fft']
	except Exception as e:
		print("ERROR reading dict: %s" % e)

	# Try reading in the other 2 tones.
	try:
		new_fest3 = in_data['f3_est']
		new_fest4 = in_data['f4_est']
		fest_data[2,-1] = new_fest3
		fest_data[3,-1] = new_fest4
	except:
		# If we can't read these tones out of the dict, fill with NaN
		fest_data[2,-1] = np.nan
		fest_data[3,-1] = np.nan

	# Add in new data points
	ebno_data[-1] = new_ebno
	ppm_data[-1] = new_ppm
	fest_data[0,-1] = new_fest1
	fest_data[1,-1] = new_fest2

	# Update plots
	spec_data_log = 20*np.log10(np.array(new_spec)+0.01)
	spec_curve.setData(spec_data_log)
	spec_plot.setYRange(spec_data_log.max()-50,spec_data_log.max()+10)
	ebno_curve.setData(x=history_scale,y=ebno_data)
	ppm_curve.setData(x=history_scale,y=ppm_data)
	fest1_curve.setData(x=history_scale,y=fest_data[0,:],pen='r') # f1 = Red
	fest2_curve.setData(x=history_scale,y=fest_data[1,:],pen='g') # f2 = Blue
	fest3_curve.setData(x=history_scale,y=fest_data[2,:],pen='b') # f3 = Green
	fest4_curve.setData(x=history_scale,y=fest_data[3,:],pen='m') # f4 = Magenta

	#Now try reading in and plotting the eye diagram
	try:
		eye_data = np.array(in_data['eye_diagram'])

		#eye_plot.disableAutoRange()
		eye_plot.clear()
		col_index = 0
		for line in eye_data:
			eye_plot.plot(line,pen=(col_index,eye_data.shape[0]))
			col_index += 1
		#eye_plot.autoRange()
		
		#Quick autoranging for x-axis to allow for differing P and Ts values
		if eye_xr != len(eye_data[0]) - 1:
			eye_xr = len(eye_data[0]) - 1
			eye_plot.setXRange(0,len(eye_data[0])-1)
			
	except Exception as e:
		pass


timer = pg.QtCore.QTimer()
timer.timeout.connect(update_plots)
timer.start(1000/update_rate)


# Thread to read from stdin and push into a queue to be processed.
def read_stdin():
	''' Read JSON data via stdin '''
	global in_queue

	while True:
		in_line = sys.stdin.readline()

		if in_line == "":
			# Empty line means stdin has been closed, so exit this thread.
			break

		if not in_queue.full():
			in_queue.put_nowait(in_line)


udp_listener_running = True

def read_udp():
    ''' Read JSON data via UDP '''
    global in_queue, args, udp_listener_running

    _s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    _s.settimeout(1)
    _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        pass
    _s.bind(('',args.udp))
    print("Started UDP Listener Thread.")
    udp_listener_running = True

    while udp_listener_running:
        try:
            m = _s.recvfrom(2048)
        except socket.timeout:
            m = None
        except:
            traceback.print_exc()
        
        if m != None:
            in_queue.put_nowait(m[0])
    
    print("Closing UDP Listener")
    _s.close()

# Start a listener thread, either UDP or stdin.
if args.udp != -1:
	read_thread = Thread(target=read_udp)
else:
	read_thread = Thread(target=read_stdin)
read_thread.daemon = True # Set as daemon, so when all other threads die, this one gets killed too.
read_thread.start()

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
	import sys
	if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
		try:
			QtGui.QApplication.instance().exec_()
		except KeyboardInterrupt:
			# Stop a UDP listener, if one is running
			udp_listener_running = False
			sys.exit(0)
