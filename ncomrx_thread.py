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

Sets up a background thread, which receives data from OxTS INSs
(on port 3000). Each IP address is send to a separate NComRx decoder.

Use by:

nrxs = ncomrx_thread.NcomRxThread()

nrxs.nrx['<ip>']['decoder'] will be an NcomRx class that can be used to
access the decoded data. For example:

  nrxs.nrx['192.168.2.62']['decoder'].nav['GpsTime']

Call nrxs.stop() to end, but note that the thread will be blocked on
data from the socket so it will only stop after data is received.
"""

import time
import socket
import ncomrx
import collections
import binascii
import threading


class NcomRxThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon_threads = True
        ncomrx.NcomRx.__init__(self)
        self.keepGoing = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', 3000))
        self.nrx = {}
        self.start()
    
    def run(self):
        while(self.keepGoing):
            # Get data from socket
            nb, addrport = self.sock.recvfrom(256) # New bytes
            myTime = time.perf_counter() # Grab time asap
            
            addr = addrport[0] # Just grab the IP address, not port
            
            # Is this a new IP address
            if addr not in self.nrx:
                # Then create a new crclist and decoder in nrx
                self.nrx[addr] = {
                    'crcList': collections.deque(maxlen=200),
                    'decoder': ncomrx.NcomRx()
                    }
                # Add IP address to connection, useful for user
                self.nrx[addr]['decoder'].connection['ip'] = addr
                self.nrx[addr]['decoder'].connection['repeatedUdp'] = 0
            
            # Under linux, UDP packets can be repeated, which messes up
            # the ncom decoding. Compute CRC and use it to identify
            # repeated packets
            crc = binascii.crc32(nb)
            if crc not in self.nrx[addr]['crcList']:
                self.nrx[addr]['crcList'].append(crc)                
                self.nrx[addr]['decoder'].decode(nb, machineTime=myTime)
                # And process all possible data
                while self.nrx[addr]['decoder'].decode(b'', machineTime=myTime):
                    pass
            else:
                self.nrx[addr]['decoder'].connection['repeatedUdp'] += 1
                                        
    def stop(self):
        self.keepGoing = False
