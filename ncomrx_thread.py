# The MIT License (MIT)

# Copyright (C) 2021 s7711
# 39369253+s7711@users.noreply.github.com

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


"""
ncomrx_thread.py

Extends ncomrx so that the decode gets data from a socket
Runs as a background thread

NOTE: this version only works when there is one NCOM broadcaster on the
network.

Use by:

nrx = ncomrx_thread.NcomRxThread()

then access dictonaries nrx.nav and nrx.status for the navigation
and status messages

Call nrx.stop() to end, but note that the thread will be blocked on
data from the socket so it will only stop after data is received.
"""


import time
import socket
import ncomrx
import collections
import binascii
import threading

#import gpiozero # Debugging


class NcomRxThread(threading.Thread, ncomrx.NcomRx):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon_threads = True
        ncomrx.NcomRx.__init__(self)
        self.keepGoing = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self.sock.bind(('', 3000))
        self.crcList = collections.deque(maxlen=200)
        #self.pin = gpiozero.LED(24) # Debugging
        #self.exceptions = 0 # Debugging
        self.start()
    
    def run(self):
        rb = b""                    # Remaining bytes from previous data
        while(self.keepGoing):
            # Get data from socket
            nb = self.sock.recv(256) # New bytes
            myTime = time.perf_counter() # Grab time asap
            
            # Remove duplicate packets by computing and testing CRC
            crc = binascii.crc32(nb)
            if crc not in self.crcList:                
                self.crcList.append(crc)
                self.decode(nb, machineTime=myTime)
                                                                                
                """
                # This code is used to test the timing by setting
                # the pin (on the raspberry pi) high when the NCOM
                # message at the start of the second is received
                try:
                    t = ((self.nav['GpsSeconds'] % 1.0) * 1000.0)
                    if t >= 0.0 and t < 9.0:
                        self.pin.on()
                    else:
                        self.pin.off()
                except:
                    self.exceptions += 1
                """
                        
    def stop(self):
        self.keepGoing = False
