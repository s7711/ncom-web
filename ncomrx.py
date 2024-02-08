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
ncomrx.py
Decoder for OxTS NCOM data stream
Decodes measurements into dictionaries
  nav - navigation measurements
  status - status and configuration
  connection - information about the decoding (characters, skipped, etc)

 Multiple dictionaries are used because the nav measurements are at 100Hz
 and the status/configuration measurements are slower

 Special packets (e.g. feature codes) are not decoded

 Reference information:
 OxTS ncom decoder in C: https://github.com/OxfordTechnicalSolutions/NCOMdecoder
 OxTS NCOM manual: https://www.oxts.com/wp-content/uploads/2017/06/ncomman.pdf
"""

import struct
import datetime
import math

########################################################################
# Definitions: from NComRx.c

NOUTPUT_PACKET_LENGTH  = 72               # NCom packet length
NCOM_SYNC           = 0xE7                # NCom sync byte
PKT_PERIOD          = 0.01                # 10ms updates
TIME2SEC            = 1e-3                # Units of 1 ms
FINETIME2SEC        = 4e-6                # Units of 4 us
TIMECYCLE           = 60000               # Units of TIME2SEC = i.e. 60 seconds
WEEK2CYCLES         = 10080               # Time cycles in a week
ACC2MPS2            = 1e-4                # Units of 0.1 mm/s^2
RATE2RPS            = 1e-5                # Units of 0.01 mrad/s
VEL2MPS             = 1e-4                # Units of 0.1 mm/s
ANG2RAD             = 1e-6                # Units of 0.001 mrad
INNFACTOR           = 0.1                 # Resolution of 0.1
POSA2M              = 1e-3                # Units of 1 mm
VELA2MPS            = 1e-3                # Units of 1 mm/s
ANGA2RAD            = 1e-5                # Units of 0.01 mrad
GB2RPS              = 5e-6                # Units of 0.005 mrad/s
AB2MPS2             = 1e-4                # Units of 0.1 mm/s^2
GSFACTOR            = 1e-6                # Units of 1 ppm
ASFACTOR            = 1e-6                # Units of 1 ppm
GBA2RPS             = 1e-6                # Units of 0.001 mrad/s
ABA2MPS2            = 1e-5                # Units of 0.01 mm/s^2
GSAFACTOR           = 1e-6                # Units of 1 ppm
ASAFACTOR           = 1e-6                # Units of 1 ppm
GPSPOS2M            = 1e-3                # Units of 1 mm
GPSATT2RAD          = 1e-4                # Units of 0.1 mrad
GPSPOSA2M           = 1e-4                # Units of 0.1 mm
GPSATTA2RAD         = 1e-5                # Units of 0.01 mrad
INNFACTOR           = 0.1                 # Resolution of 0.1
DIFFAGE2SEC         = 1e-2                # Units of 0.01 s
REFPOS2M            = 0.0012              # Units of 1.2 mm
REFANG2RAD          = 1e-4                # Units of 0.1 mrad
OUTPOS2M            = 1e-3                # Units of 1 mm
ZVPOS2M             = 1e-3                # Units of 1 mm
ZVPOSA2M            = 1e-4                # Units of 0.1 mm
NSPOS2M             = 1e-3                # Units of 1 mm
NSPOSA2M            = 1e-4                # Units of 0.1 mm
ALIGN2RAD           = 1e-4                # Units of 0.1 mrad
ALIGNA2RAD          = 1e-5                # Units of 0.01 mrad
SZVDELAY2S          = 1.0                 # Units of 1.0 s
SZVPERIOD2S         = 0.1                 # Units of 0.1 s
TOPSPEED2MPS        = 0.5                 # Units of 0.5 m/s
NSDELAY2S           = 0.1                 # Units of 0.1 s
NSPERIOD2S          = 0.02                # Units of 0.02 s
NSACCEL2MPS2        = 0.04                # Units of 0.04 m/s^2
NSSPEED2MPS         = 0.1                 # Units of 0.1 m/s
NSRADIUS2M          = 0.5                 # Units of 0.5 m
INITSPEED2MPS       = 0.1                 # Units of 0.1 m/s
HLDELAY2S           = 1.0                 # Units of 1.0 s
HLPERIOD2S          = 0.1                 # Units of 0.1 s
STATDELAY2S         = 1.0                 # Units of 1.0 s
STATSPEED2MPS       = 0.01                # Units of 1.0 cm/s
WSPOS2M             = 1e-3                # Units of 1 mm
WSPOSA2M            = 1e-4                # Units of 0.1 mm
WSSF2PPM            = 0.1                 # Units of 0.1 pulse per metre = ppm
WSSFA2PC            = 0.002               # Units of 0.002% of scale factor
WSDELAY2S           = 0.1                 # Units of 0.1 s
WSNOISE2CNT         = 0.1                 # Units of 0.1 count for wheel speed noise
UNDUL2M             = 0.005               # Units of 5 mm
DOPFACTOR           = 0.1                 # Resolution of 0.1
OMNISTAR_MIN_FREQ   = 1.52e9              # = Hz i.e. 1520.0 MHz
OMNIFREQ2HZ         = 1000.0              # Resolution of 1 kHz
SNR2DB              = 0.2                 # Resolution of 0.2 dB
LTIME2SEC           = 1.0                 # Resolution of 1.0 s
TEMPK_OFFSET        = 203.15              # Temperature offset in degrees K
ABSZERO_TEMPC       = -273.15             # Absolute zero = i.e. 0 deg K in deg C
FINEANG2RAD         = 1.74532925199433e-9 # Units of 0.1 udeg
ALT2M               = 1e-3                # Units of 1 mm
SUPPLYV2V           = 0.1                 # Units of 0.1 V
SP2M                = 1e-3                # Units of 1mm

RAD2DEG             = 57.29577951308232   # 180/pi
DEG2RAD             = 1.0/RAD2DEG


# WGS-84 constants, for reference frame calculations
EARTH_EQUAT_RADIUS  = (6378137.0)         # m
EARTH_POLAR_RADIUS  = (6356752.3142)      # m
EARTH_MEAN_RADIUS   = (6367435.68)        # m
EARTH_FLATTENING    = (3.35281066475e-3)
EARTH_ECCENTRICITY  = (0.0818191908426)


########################################################################
# Other constants
# Note: GPS time isn't really UTC, so be careful with this
GPS_STARTTIME = datetime.datetime(1980,1,6,tzinfo=datetime.timezone.utc)


########################################################################
# NCOM class
class NcomRx(object):
    def __init__(self):
        # todo: protect nav, status with a lock when multi-threaded
        self.nav = {}  # Dictionary for navigation measurements
        self.status = {} # Dictionary for status/configuration
        self.connection = {} # Dictionary for decoding status variables
        self.ncomBytes = b'' # Holds bytes waiting to be decoded
        
        # Find all 'decodeStatus' functions and create dictionary
        decodeList = [ (int(decoder[12:]),getattr(self,decoder)) for decoder in dir(self) if decoder[0:12] == 'decodeStatus']
        self.decodeStatus = dict(decodeList)
        self.connection['decodeStatusErrors'] = {} # Useful for debugging or identifying new status channels
        
        # A race-condition exists with time, where minutes are in
        # a status message and seconds are in Batch A
        # Store previous seconds to figure out if they have wrapped
        self.previousSeconds = 0
        
        # Information about decoding the stream
        self.connection['numChars'] = 0
        self.connection['skippedChars'] = 0
        self.connection['numPackets'] = 0        
        
        # Filter for converting machineTime to GpsTime
        self.connection['timeOffset'] = None   # GpsTime = machineTime + timeOffset
        self.f1 = 0.1            # Factor to decrease timeOffset
        self.f2 = 0.001          # Factor to increase timeOffset

    ####################################################################
    # decode() is the normal function to call when new data is available
    # It will update the nav, status and connection dictionaries with
    # new measurements.
    # Only one packet will be decoded so either ensure that
    # rxBytes <= NOUTPUT_PACKET_LENGTH or call multiple times until
    # return value is 0
    def decode(self,rxBytes, machineTime=None):
        # ncomBytes should be a bytes object
        # Returns 1 if packet is decoded
        # Returns 0 if packet cannot be decoded
        # machineTime can be used to work out the offset between the
        #   local clock and GpsTime
        
        self.ncomBytes += rxBytes # Add received bytes to ncomBytes
        
        # Find the first valid packet
        skipped = 0
        while True:
            # Find the NCOM_SYNC
            syncOffset = self.ncomBytes.find(NCOM_SYNC)
            
            # -1 means there is no sync or valid packet in ncomBytes
            if syncOffset < 0:
                skipped += len(self.ncomBytes)
                self.connection['numChars'] += skipped
                self.connection['skippedChars'] += skipped
                self.ncomBytes = b''
                return 0
            
            # Realign to sync byte
            self.ncomBytes = self.ncomBytes[syncOffset:]
            skipped += syncOffset
            
            # Is there enough data for a full packet?
            if len(self.ncomBytes) < NOUTPUT_PACKET_LENGTH:
                return 0
                        
            # Test the packet integrity
            if self.ncomBytes[22] == sum(self.ncomBytes[1:22]) % 256 \
            or self.ncomBytes[61] == sum(self.ncomBytes[1:61]) % 256 \
            or self.ncomBytes[71] == sum(self.ncomBytes[1:71]) % 256:
                self.connection['numChars'] += NOUTPUT_PACKET_LENGTH
                self.connection['skippedChars'] += skipped
                self.connection['numPackets'] += 1
                break # Valid packet
            
            # This sync is not a valid packet so skip over
            self.ncomBytes = self.ncomBytes[1:]
            skipped += 1
        
        # ... Must have a valid packet or we would have returned
        # Decode NavStatus to find what other fields are valid
        self.nav['NavStatus'] = int(self.ncomBytes[21])
        self.status['NavStatus'] = int(self.ncomBytes[21])
        
        if self.nav['NavStatus'] in [0,5,6,7]:
            self.status = {}
            # Remove this packet
            self.ncomBytes = self.ncomBytes[NOUTPUT_PACKET_LENGTH:]
            self.connection['unprocessedBytes'] = len(self.ncomBytes)
            return 1 # All quantities are invalid
        
        if self.nav['NavStatus'] in [1,2,3,4,20,21,22]:        
            # Decode Batch A
            self.nav['GpsSeconds'] = int.from_bytes(self.ncomBytes[1:3], byteorder = 'little', signed=False) * TIME2SEC
            self.nav['Ax'] = int.from_bytes(self.ncomBytes[3:6],   byteorder = 'little', signed=True) * ACC2MPS2
            self.nav['Ay'] = int.from_bytes(self.ncomBytes[6:9],   byteorder = 'little', signed=True) * ACC2MPS2
            self.nav['Az'] = int.from_bytes(self.ncomBytes[9:12],  byteorder = 'little', signed=True) * ACC2MPS2
            self.nav['Wx'] = int.from_bytes(self.ncomBytes[12:15], byteorder = 'little', signed=True) * RATE2RPS * RAD2DEG
            self.nav['Wy'] = int.from_bytes(self.ncomBytes[15:18], byteorder = 'little', signed=True) * RATE2RPS * RAD2DEG
            self.nav['Wz'] = int.from_bytes(self.ncomBytes[18:21], byteorder = 'little', signed=True) * RATE2RPS * RAD2DEG

            # Create sensible time format
            # See if seconds have wrapped
            if self.previousSeconds > 30.0 and self.nav['GpsSeconds'] < 30.0:
                try:
                    self.status['GpsMinutes'] += 1
                except:
                    pass
            self.previousSeconds = self.nav['GpsSeconds']
            try:
                self.nav['GpsTime'] = GPS_STARTTIME + \
                    datetime.timedelta( minutes=self.status['GpsMinutes'], seconds=self.nav['GpsSeconds'] )
                self.status['GpsTime'] = self.nav['GpsTime']
                self.nav['UtcTime'] = self.nav['GpsTime'] + \
                    datetime.timedelta( seconds=self.status['TimeUtcOffset'] )
                self.status['UtcTime'] = self.nav['UtcTime']
            except: # Most likely is that 'GpsMinutes' or 'TimeUtcOffset' is not available
                pass
            
            # todo: if time jumps too far (from last packet decode) then
            # invalidate status because holding old values is not
            # sensible
            
            # Filter timeOffset for machine time to GpsTime conversion
            # todo: Maybe put this code in a separate class/function
            # so that different estimators can be tried
            try:
                if machineTime == None:
                    self.connection['timeOffset'] = None
                elif self.connection['timeOffset'] == None:
                    self.connection['timeOffset'] = self.nav['GpsSeconds'] + self.status['GpsMinutes'] * 60.0 - machineTime
                else:
                    to = self.nav['GpsSeconds'] + self.status['GpsMinutes'] * 60.0 - machineTime
                    dto = to - self.connection['timeOffset'] # This is the unfiltered adjustment for this epoch
                    self.connection['timeOffset'] += dto*self.f2 if dto < 0.0 else dto*self.f1
            except:
                self.connection['timeOffset'] = None
            
        if self.nav['NavStatus'] in [3,4,20,21,22]:
            # Decode Batch B
            self.nav['Lat'] = struct.unpack("<d",self.ncomBytes[23:31])[0] # Note: radians
            self.nav['Lon'] = struct.unpack("<d",self.ncomBytes[31:39])[0] # Note: radians
            self.nav['Alt'] = struct.unpack("<f",self.ncomBytes[39:43])[0]
            self.nav['Vn'] = int.from_bytes(self.ncomBytes[43:46], byteorder = 'little', signed=True) * VEL2MPS
            self.nav['Ve'] = int.from_bytes(self.ncomBytes[46:49], byteorder = 'little', signed=True) * VEL2MPS
            self.nav['Vd'] = int.from_bytes(self.ncomBytes[49:52], byteorder = 'little', signed=True) * VEL2MPS
            h = int.from_bytes(self.ncomBytes[52:55], byteorder = 'little', signed=True) * ANG2RAD * RAD2DEG
            self.nav['Heading'] = h if h >= 0.0 else h + 360.0
            self.nav['Pitch']   = int.from_bytes(self.ncomBytes[55:58], byteorder = 'little', signed=True) * ANG2RAD * RAD2DEG
            self.nav['Roll']    = int.from_bytes(self.ncomBytes[58:61], byteorder = 'little', signed=True) * ANG2RAD * RAD2DEG

        if self.nav['NavStatus'] in [1,2,3,4,10,20,21,22]:
            # Decode Batch S
            statusChannel = int(self.ncomBytes[62])
            try:
                self.decodeStatus[statusChannel](self.ncomBytes[63:71])
            except:
                # Catch missing or erroneous decodeStatus functions
                try:
                    # Increment the errors for this channel
                    self.connection['decodeStatusErrors'][statusChannel] += 1
                except:
                    self.connection['decodeStatusErrors'][statusChannel] = 1 # Start new key

        # Remove this packet
        self.ncomBytes = self.ncomBytes[NOUTPUT_PACKET_LENGTH:]
        self.connection['unprocessedBytes'] = len(self.ncomBytes)

        return 1


    def mt2Gps(self, machineTime):
        # Converts machineTime to GpsTime
        # todo: return the stdev estimate as well as the converted time
        if self.connection['timeOffset'] != None:
            gt = machineTime + self.connection['timeOffset']
            return GPS_STARTTIME + datetime.timedelta( seconds=machineTime+self.connection['timeOffset'] )
        else:
            return None


    ####################################################################
    # Decoders for status channels.
    #
    # "invalid" measurements are added then removed. While this is more
    # CPU intensive, it does reduce source code significantly
    
    def decodeStatus0(self,statusBytes):
        # Full time, number of satellites, position mode, velocity mode, dual antenna mode
        # 'Gps' not 'Gnss' used for historical reasons
        self.status['GpsMinutes'] = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=False)
        if self.status['GpsMinutes'] < 1000: del self.status['GpsMinutes']
        
        self.status['GpsNumObs'] = int(statusBytes[4])
        if self.status['GpsNumObs'] == 255: del self.status['GpsNumObs']

        self.status['GpsPosMode'] = int(statusBytes[5])
        if self.status['GpsPosMode'] == 255: del self.status['GpsPosMode']

        self.status['GpsVelMode'] = int(statusBytes[6])
        if self.status['GpsVelMode'] == 255: del self.status['GpsVelMode']

        self.status['GpsAttMode'] = int(statusBytes[7])
        if self.status['GpsAttMode'] == 255: del self.status['GpsAttMode']


    def decodeStatus1(self,statusBytes):
        # Kalman filter innovations set 1 (position, velocity, attitude)
        self._updateInnovation( 'InnPosX', statusBytes[0:1] )
        self._updateInnovation( 'InnPosY', statusBytes[1:2] )
        self._updateInnovation( 'InnPosZ', statusBytes[2:3] )
        self._updateInnovation( 'InnVelX', statusBytes[3:4] )
        self._updateInnovation( 'InnVelY', statusBytes[4:5] )
        self._updateInnovation( 'InnVelZ', statusBytes[5:6] )
        self._updateInnovation( 'InnHeading', statusBytes[6:7] )
        self._updateInnovation( 'InnPitch', statusBytes[7:8] )


    def _updateInnovation(self, k, b ):
        # Updating innovations is a little long-winded and repeative
        # so this function tidies things up
        # Both the actual value and a "filtered" value are added
        # The "filtered" value is usually more useful
        # The filter is non-linear. The abs() of the innovation is used
        # and larger innovations are not filtered whereas smaller ones
        # decay slowly
        # k is the key (and "Filt" is added for the filtered versions
        # b is the bytes array from statusBytes
        inn = (int.from_bytes(b, byteorder = 'little', signed=True)>>1) * INNFACTOR
        if b[0]&0x1 == 0x0:
            if k in self.status:
                del self.status[k]
        else:
            self.status[k] = inn # add/update this innovation
            
            inn = abs(inn)       # abs() for filtering
            kf = k + 'Filt'      # filtered key
            if kf not in self.status:
                self.status[kf] = inn    # New, so add the filtered key
            elif inn > self.status[kf]:  # innovation larger (than filtered key)
                self.status[kf] = inn    # so let it jump straight to the new value
            else:                        # Else decay slowly - not an exact filter
                self.status[kf] = 0.9 * self.status[kf] + 0.1 * inn


    def _updateLE16(self, s, measurement ):
        # Some NCOM measurements are transmitted with only the
        # lower 16-bits (to save space). Their exact value is not
        # critical but it is good to see that they are changing
        # This function updates a status 'measurement' with the
        # lower 16-bits in s. When s wraps, the upper part is
        # incremented.
        # s is an unsigned int
        # measurement is the string representing the status measurement
        
        # Get the current measurement
        try:
            i = self.status[measurement]
        except:
            i = 0

        # Split into lower and upper parts
        il = i & 0xFFFF
        iu = i >> 16
        
        if (il > s): # Indicates s has wrapped
            iu += 1
        
        self.status[measurement] = (iu<<16) + s


    def _updateLE8(self, s, measurement ):
        # 8-bit equivalent of _updateLE16
        # s is an unsigned int
        # measurement is the string representing the status measurement
        
        # Get the current measurement
        try:
            i = self.status[measurement]
        except:
            i = 0

        # Split into lower and upper parts
        il = i & 0xFF
        iu = i >> 8
        
        if (il > s): # Indicates s has wrapped
            iu += 1
        
        self.status[measurement] = (iu<<8) + s        


    def _updateLE32(self, s, measurement ):
        # 32-bit equivalent of _updateLE16
        # s is an unsigned int
        # measurement is the string representing the status measurement
        
        # Get the current measurement
        try:
            i = self.status[measurement]
        except:
            i = 0

        # Split into lower and upper parts
        il = i & 0xFFFFFFFF
        iu = i >> 32
        
        if (il > s): # Indicates s has wrapped
            iu += 1
        
        self.status[measurement] = (iu<<32) + s        


    def decodeStatus2(self,statusBytes):
        # Internal information about primary GNSS receiver
        self._updateLE16(int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False),'GpsPrimaryChars')
        self._updateLE16(int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False),'GpsPrimaryPkts')
        self._updateLE16(int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False),'GpsPrimaryCharsSkipped')
        self._updateLE16(int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False),'GpsPrimaryOldPkts')

    def decodeStatus3(self,statusBytes):
        # Position accuracy
        self.status['NorthAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * POSA2M
        self.status['EastAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * POSA2M
        self.status['AltAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * POSA2M
        if statusBytes[6] > 150:
            del self.status['NorthAcc']
            del self.status['EastAcc']
            del self.status['AltAcc']       

        # ABD robot UMAC interface status byte
        self.status['UmacStatus'] = statusBytes[7]
        if statusBytes[7] == 0xFF: del self.status['UmacStatus']


    def decodeStatus4(self,statusBytes):
        # Velocity accuracy
        self.status['VnAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * VELA2MPS
        self.status['VeAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * VELA2MPS
        self.status['VdAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * VELA2MPS
        if statusBytes[6] > 150:
            del self.status['VnAcc']
            del self.status['VeAcc']
            del self.status['VdAcc']       

        # Processing method used by blended
        self.status['BlendedMethod'] = statusBytes[7]
        if statusBytes[7] == 0: del self.status['BlendedMethod']


    def decodeStatus5(self,statusBytes):
        # Orientation accuracy
        self.status['HeadingAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * ANGA2RAD * RAD2DEG
        self.status['PitchAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * ANGA2RAD * RAD2DEG
        self.status['RollAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * ANGA2RAD * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['HeadingAcc']
            del self.status['PitchAcc']
            del self.status['RollAcc']       


    def decodeStatus6(self,statusBytes):
        # Gyro bias
        self.status['WxBias'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GB2RPS * RAD2DEG
        self.status['WyBias'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GB2RPS * RAD2DEG
        self.status['WzBias'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GB2RPS * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['WxBias']
            del self.status['WyBias']
            del self.status['WzBias']       


    def decodeStatus7(self,statusBytes):
        # Accelerometer bias
        self.status['AxBias'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * AB2MPS2
        self.status['AyBias'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * AB2MPS2
        self.status['AzBias'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * AB2MPS2
        if statusBytes[6] > 150:
            del self.status['AxBias']
            del self.status['AyBias']
            del self.status['AzBias']       


    def decodeStatus8(self,statusBytes):
        # Gyro scale factor
        self.status['WxSf'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GSFACTOR
        self.status['WySf'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GSFACTOR
        self.status['WzSf'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GSFACTOR
        if statusBytes[6] > 150:
            del self.status['WxSf']
            del self.status['WySf']
            del self.status['WzSf']       


    def decodeStatus9(self,statusBytes):
        # Gyro bias accuracy
        self.status['WxBiasAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * GBA2RPS * RAD2DEG
        self.status['WyBiasAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * GBA2RPS * RAD2DEG
        self.status['WzBiasAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * GBA2RPS * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['WxBiasAcc']
            del self.status['WyBiasAcc']
            del self.status['WzBiasAcc']       


    def decodeStatus10(self,statusBytes):
        # Accelerometer bias accuracy
        self.status['AxBiasAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * ABA2MPS2
        self.status['AyBiasAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * ABA2MPS2
        self.status['AzBiasAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * ABA2MPS2
        if statusBytes[6] > 150:
            del self.status['AxBiasAcc']
            del self.status['AyBiasAcc']
            del self.status['AzBiasAcc']       


    def decodeStatus11(self,statusBytes):
        # Gyro scale factor accuracy
        self.status['WxSfAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * GSAFACTOR
        self.status['WySfAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * GSAFACTOR
        self.status['WzSfAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * GSAFACTOR
        if statusBytes[6] > 150:
            del self.status['WxSfAcc']
            del self.status['WySfAcc']
            del self.status['WzSfAcc']       


    def decodeStatus12(self,statusBytes):
        # Position estimate of primary GPS antenna lever-arm
        self.status['GAPx'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSPOS2M
        self.status['GAPy'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSPOS2M
        self.status['GAPz'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GPSPOS2M
        if statusBytes[6] > 150:
            del self.status['GAPx']
            del self.status['GAPy']
            del self.status['GAPz']       


    def decodeStatus13(self,statusBytes):
        # Orientation estimate of dual antenna systems
        self.status['AtH'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['AtP'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['BaseLineLength'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * GPSPOS2M
        if statusBytes[6] > 150:
            del self.status['AtH']
            del self.status['AtP']
            del self.status['BaseLineLength']       


    def decodeStatus14(self,statusBytes):
        # Position estimate of primary GPS antenna lever-arm accuracy
        self.status['GAPxAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * GPSPOSA2M
        self.status['GAPyAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * GPSPOSA2M
        self.status['GAPzAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * GPSPOSA2M
        if statusBytes[6] > 150:
            del self.status['GAPxAcc']
            del self.status['GAPyAcc']
            del self.status['GAPzAcc']


    def decodeStatus15(self,statusBytes):
        # Orientation estimate of dual antenna systems accuracy
        self.status['AtHAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * GPSATTA2RAD * RAD2DEG
        self.status['AtPAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * GPSATTA2RAD * RAD2DEG
        self.status['BaseLineLengthAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * GPSPOSA2M
        if statusBytes[6] > 150:
            del self.status['AtHAcc']
            del self.status['AtPAcc']
            del self.status['BaseLineLengthAcc']


    def decodeStatus16(self,statusBytes):
        # RT to vehicle rotation
        self.status['VehHeading'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['VehPitch'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['VehRoll'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['VehHeading']
            del self.status['VehPitch']
            del self.status['VehRoll']       

        self.status['TimeUtcOffset'] = int.from_bytes(statusBytes[7:8], byteorder = 'little', signed=True) >> 1
        if statusBytes[7]&0x1 == 0: del self.status['TimeUtcOffset']


    def decodeStatus17(self,statusBytes):
        # Internal information about secondary GNSS receiver
        self._updateLE16(int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False),'GpsSecondaryChars')
        self._updateLE16(int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False),'GpsSecondaryPkts')
        self._updateLE16(int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False),'GpsSecondaryCharsSkipped')
        self._updateLE16(int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False),'GpsSecondaryOldPkts')


    def decodeStatus18(self,statusBytes):
        # Internal information about the inertial measurement unit
        self._updateLE32(int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=False),'ImuChars')
        self._updateLE16(int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False),'ImuPkts')
        self._updateLE16(int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False),'ImuSkipped')


    def decodeStatus19(self,statusBytes):
        # Software version running on the RT
        self.status['DevId'] = statusBytes.decode('utf-8')


    def decodeStatus20(self,statusBytes):
        # Differential corrections configuration
        self.status['GpsDiffAge'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * DIFFAGE2SEC
        self.status['BaseStationId'] = statusBytes[2:6].decode('utf-8')
        if statusBytes[2] == 0: del self.status['BaseStationId']


    def decodeStatus21(self,statusBytes):
        # Disk space and size of current internal log file
        self.status['DiskSpace'] = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=False)
        self.status['FileSize'] = int.from_bytes(statusBytes[4:8], byteorder = 'little', signed=False)
        

    def decodeStatus22(self,statusBytes):
        # Internal information on timing of real-time processing
        self.status['TimeMismatch'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False)
        if self.status['TimeMismatch'] == 65535: del self.status['TimeMismatch']
        
        self.status['ImuTimeDiff'] = statusBytes[2]
        if statusBytes[2] == 255: del self.status['ImuTimeDiff']

        self.status['ImuTimeMargin'] = statusBytes[3]
        if statusBytes[3] == 255: del self.status['ImuTimeMargin']

        self.status['ImuLoopTime'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        if self.status['ImuLoopTime'] == 65535: del self.status['ImuLoopTime']

        self.status['OpLoopTime'] = int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False)
        if self.status['OpLoopTime'] == 65535: del self.status['OpLoopTime']


    def decodeStatus23(self,statusBytes):
        # System up time and consecutive GPS rejections
        self.status['BnsLag'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False)
        if self.status['BnsLag'] == 65535: del self.status['BnsLag']
        
        x = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False)
        if x > 20700: self.status['UpTime'] = (x-20532)*3600
        elif x < 10800: self.status['UpTime'] = x
        else: self.status['UpTime'] = (x-10620)*60
        
        self.status['GpsPosReject'] = statusBytes[4]
        if statusBytes[4] == 255: del self.status['GpsPosReject']
        
        self.status['GpsVelReject'] = statusBytes[5]
        if statusBytes[5] == 255: del self.status['GpsVelReject']

        self.status['GpsAttReject'] = statusBytes[6]
        if statusBytes[6] == 255: del self.status['GpsAttReject']


    def decodeStatus24(self,statusBytes):
        # Trigger 1 event timings (falling edge triggers)
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Trig1FallingTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Trig1FallingTime']
        
        self.status['Trig1FallingCount'] = statusBytes[7]

    # decodeStatus25 not decoded: reserved
    # Status 25 used by older OxTS systems and unlikely to be output
    # by any firmware after 2010. Status 66/67 used now.
    
    def decodeStatus26(self,statusBytes):
        # Remote lever-arm
        self.status['RemoveLeverArmX'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * OUTPOS2M
        self.status['RemoveLeverArmY'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * OUTPOS2M
        self.status['RemoveLeverArmZ'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * OUTPOS2M
        if statusBytes[6] > 0:
            del self.status['RemoveLeverArmX']
            del self.status['RemoveLeverArmY']
            del self.status['RemoveLeverArmZ']       

    def decodeStatus27(self,statusBytes):
        # Internal information about dial antenna ambiguity search
        self.status['HeadQuality'] = statusBytes[0]
        self.status['HeadSearchType'] = statusBytes[1]
        self.status['HeadSearchStatus'] = statusBytes[2]
        self.status['HeadSearchReady'] = statusBytes[3]
        
        self.status['HeadSearchInit'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        if self.status['HeadSearchInit'] == 0xFFFF: del self.status['HeadSearchInit']
        
        self.status['HeadSearchNum'] = int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False)
        if self.status['HeadSearchNum'] == 0xFFFF: del self.status['HeadSearchNum']
    
    def decodeStatus28(self,statusBytes):
        # Details on initial settings for heading ambiguity search
        self.status['HeadSearchMaster'] = 1 + statusBytes[0]
        self.status['HeadSearchSlave1'] = 1 + statusBytes[1]
        self.status['HeadSearchSlave2'] = 1 + statusBytes[2]
        self.status['HeadSearchSlave3'] = 1 + statusBytes[3]
        self.status['HeadSearchTime'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        self.status['HeadSearchConstr'] = int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False)
        
    def decodeStatus29(self,statusBytes):
        # Details on the initial settings
        self.status['OptionLevel'] = statusBytes[0]
        if (statusBytes[0]&0x80) == 0x80: del self.status['OptionLevel']
        
        self.status['OptionVibration'] = statusBytes[1]
        if (statusBytes[1]&0x80) == 0x80: del self.status['OptionVibration']

        self.status['OptionGpsAcc'] = statusBytes[2]
        if (statusBytes[2]&0x80) == 0x80: del self.status['OptionGpsAcc']

        self.status['OptionUpd'] = statusBytes[3]
        if (statusBytes[3]&0x80) == 0x80: del self.status['OptionUpd']

        self.status['OptionsSer1'] = statusBytes[4]
        if (statusBytes[4]&0x80) == 0x80: del self.status['OptionsSer1']

        self.status['OptionsSer2'] = statusBytes[5]
        if (statusBytes[5]&0x80) == 0x80: del self.status['OptionsSer2']

        self.status['OptionHeading'] = statusBytes[6]
        if (statusBytes[6]&0x80) == 0x80: del self.status['OptionHeading']

        self.status['OptionHeave'] = statusBytes[7]
        if (statusBytes[7]&0x80) == 0x80: del self.status['OptionHeave']


    def decodeStatus30(self,statusBytes):
        # Operating system and script version information
        self.status['OsVersion1'] = statusBytes[0]
        if statusBytes[0] == 0xFF: del self.status['OsVersion1']
        
        self.status['OsVersion2'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['OsVersion2']

        self.status['OsVersion3'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['OsVersion3']
        
        x = int.from_bytes(statusBytes[3:6], byteorder = 'little', signed=True)
        self.status['OsScriptId'] = "%06d" % x
        if x < 0: del self.status['OsScriptId']
        
        self.status['SerialNumber'] = int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False)
        # Not going to invalidate this one 0xFFFF is invalid


    def decodeStatus31(self,statusBytes):
        # Hardware configuration information
        self.status['ImuType'] = statusBytes[0]
        if statusBytes[0] == 0xFF: del self.status['ImuType']
        
        self.status['GpsPrimary'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['GpsPrimary']

        self.status['GpsSecondary'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['GpsSecondary']

        self.status['InterPcbType'] = statusBytes[3]
        if statusBytes[3] == 0xFF: del self.status['InterPcbType']

        self.status['FrontPcbType'] = statusBytes[4]
        if statusBytes[4] == 0xFF: del self.status['FrontPcbType']

        self.status['InterSwId'] = statusBytes[5]
        if statusBytes[5] == 0xFF: del self.status['InterSwId']

        self.status['HwConfig'] = statusBytes[6]
        if statusBytes[6] == 0xFF: del self.status['HwConfig']

        gf = ~statusBytes[7]
        self.status['PsrDiffEnabled'] = (gf & 0x01) > 0
        self.status['SBASEnabled']    = (gf & 0x02) > 0
        self.status['OmniVBSEnabled'] = (gf & 0x08) > 0
        self.status['OmniHpEnabled']  = (gf & 0x10) > 0
        self.status['L1DiffEnabled']  = (gf & 0x20) > 0
        self.status['L2DiffEnabled']  = (gf & 0x40) > 0
        if (gf & 0x80) == 0:
            del self.status['PsrDiffEnabled']
            del self.status['SBASEnabled']
            del self.status['OmniVBSEnabled']
            del self.status['OmniHpEnabled']
            del self.status['L1DiffEnabled']
            del self.status['L2DiffEnabled']


    def decodeStatus32(self,statusBytes):
        # Kalman filter innovations for zero velocity, advanced slip, etc.
        self._updateInnovation( 'InnZeroVelX', statusBytes[0:1] )
        self._updateInnovation( 'InnZeroVelY', statusBytes[0:1] )
        self._updateInnovation( 'InnZeroVelZ', statusBytes[0:1] )
        self._updateInnovation( 'InnNoSlipH', statusBytes[0:1] )
        self._updateInnovation( 'InnHeadingH', statusBytes[0:1] )
        self._updateInnovation( 'InnWSpeed', statusBytes[0:1] )
        self._updateInnovation( 'InnZeroVelX', statusBytes[0:1] )
        self._updateInnovation( 'InnZeroVelX', statusBytes[0:1] )
                
    
    def decodeStatus33(self,statusBytes):
        # Zero velocity lever arm
        self.status['ZeroVelLeverArmX'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * ZVPOS2M
        self.status['ZeroVelLeverArmY'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * ZVPOS2M
        self.status['ZeroVelLeverArmZ'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * ZVPOS2M
        if statusBytes[6] > 0:
            del self.status['ZeroVelLeverArmX']
            del self.status['ZeroVelLeverArmY']
            del self.status['ZeroVelLeverArmZ']       
    
        
    def decodeStatus34(self,statusBytes):
        # Zero velocity lever arm accuracy
        self.status['ZeroVelLeverArmXAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * ZVPOSA2M
        self.status['ZeroVelLeverArmYAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * ZVPOSA2M
        self.status['ZeroVelLeverArmZAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * ZVPOSA2M
        if statusBytes[6] > 0:
            del self.status['ZeroVelLeverArmXAcc']
            del self.status['ZeroVelLeverArmYAcc']
            del self.status['ZeroVelLeverArmZAcc']       


    def decodeStatus35(self,statusBytes):
        # Advanced slip lever arm
        self.status['NoSlipLeverArmX'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * NSPOS2M
        self.status['NoSlipLeverArmY'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * NSPOS2M
        self.status['NoSlipLeverArmZ'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * NSPOS2M
        if statusBytes[6] > 0:
            del self.status['NoSlipLeverArmX']
            del self.status['NoSlipLeverArmY']
            del self.status['NoSlipLeverArmZ']       


    def decodeStatus36(self,statusBytes):
        # Advanced slip lever arm accuracy
        self.status['NoSlipLeverArmXAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * NSPOSA2M
        self.status['NoSlipLeverArmYAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * NSPOSA2M
        self.status['NoSlipLeverArmZAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * NSPOSA2M
        if statusBytes[6] > 0:
            del self.status['NoSlipLeverArmXAcc']
            del self.status['NoSlipLeverArmYAcc']
            del self.status['NoSlipLeverArmZAcc']       

    def decodeStatus37(self,statusBytes):
        # Heading misalignment angle and accuracy
        self.status['HeadingMisAlign'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * ALIGN2RAD * RAD2DEG
        self.status['HeadingMisAlignAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * ALIGNA2RAD * RAD2DEG
        if statusBytes[6] > 0:
            del self.status['HeadingMisAlign']
            del self.status['HeadingMisAlignAcc']
        
        # NCOM manual version 180806 shows validity as not 0xF,
        # but I assume this is incorrect. 0xFF used here
        self.status['NumSatsUsedPos'] = statusBytes[4]
        if statusBytes[4] == 0xFF: del self.status['NumSatsUsedPos']
        
        self.status['NumSatsUsedVel'] = statusBytes[5]
        if statusBytes[5] == 0xFF: del self.status['NumSatsUsedVel']

        self.status['NumSatsUsedAtt'] = statusBytes[7]
        if statusBytes[7] == 0xFF: del self.status['NumSatsUsedAtt']


    def decodeStatus38(self,statusBytes):
        # Zero velocity option settings
        self.status['OptionSZVDelay'] = statusBytes[0] * SZVDELAY2S
        if statusBytes[0] == 0xFF: del self.status['OptionSZVDelay']
        
        self.status['OptionSZVPeriod'] = statusBytes[1] * SZVPERIOD2S
        if statusBytes[1] == 0xFF: del self.status['OptionSZVPeriod']

        self.status['OptionTopSpeed'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * TOPSPEED2MPS
        if statusBytes[2:4] == b'\xFF\xFF': del self.status['OptionTopSpeed']
        
        self.status['OptionInitSpeed'] = statusBytes[4] * INITSPEED2MPS
        if statusBytes[4] == 0xFF: del self.status['OptionInitSpeed']
        
        self.status['OptionSer3'] = statusBytes[5]
        if statusBytes[5]&0x80 > 0: del self.status['OptionSer3']
        
    
    def decodeStatus39(self,statusBytes):
        # No slip option settings
        self.status['OptionNSDelay'] = statusBytes[0] * NSDELAY2S
        if statusBytes[0] == 0xFF: del self.status['OptionNSDelay']
        
        self.status['OptionNSPeriod'] = statusBytes[1] * NSPERIOD2S
        if statusBytes[1] == 0xFF: del self.status['OptionNSPeriod']
        
        self.status['OptionNSAngleStd'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * ANGA2RAD * RAD2DEG
        if statusBytes[2:4] == b'\xFF\xFF': del self.status['OptionNSAngleStd']
        
        self.status['OptionNSHAccel'] = statusBytes[4] * NSACCEL2MPS2
        if statusBytes[4] == 0xFF: del self.status['OptionNSHAccel']
        
        self.status['OptionNSVAccel'] = statusBytes[5] * NSACCEL2MPS2
        if statusBytes[5] == 0xFF: del self.status['OptionNSVAccel']

        self.status['OptionNSSpeed'] = statusBytes[6] * NSSPEED2MPS
        if statusBytes[6] == 0xFF: del self.status['OptionNSSpeed']

        self.status['OptionNSRadius'] = statusBytes[7] * NSRADIUS2M
        if statusBytes[7] == 0xFF: del self.status['OptionNSRadius']

    # decodeStatus40: NCOM format encoder version: not decoded
    
    def decodeStatus41(self,statusBytes):
        self.status['OptionSer1Baud'] = statusBytes[0] & 0xF
        self.status['OptionSer2Baud'] = statusBytes[1] & 0xF
        self.status['OptionSer3Baud'] = statusBytes[2] & 0xF
        self.status['OptionCanBaud']  = statusBytes[3] & 0xF
    
    
    def decodeStatus42(self,statusBytes):
        # Heading lock options
        self.status['OptionHLDelay'] = statusBytes[0] * HLDELAY2S
        if statusBytes[0] == 0xFF: del self.status['OptionHLDelay']
        
        self.status['OptionHLPeriod'] = statusBytes[1] * HLPERIOD2S
        if statusBytes[1] == 0xFF: del self.status['OptionHLPeriod']
        
        self.status['OptionHLAngleStd'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * ANGA2RAD * RAD2DEG
        if statusBytes[2:4] == b'\xFF\xFF': del self.status['OptionHLAngleStd']
        
        self.status['OptionStatDelay'] = statusBytes[4] * STATDELAY2S
        if statusBytes[4] == 0xFF: del self.status['OptionStartDelay']

        self.status['OptionStatSpeed'] = statusBytes[5] * STATSPEED2MPS
        if statusBytes[5] == 0xFF: del self.status['OptionStatSpeed']


    def decodeStatus43(self,statusBytes):
        # Trigger 1 event timing (rising edge triggers)
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Trig1RisingTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Trig1RisingTime']
        
        self.status['Trig1RisingCount'] = statusBytes[7]


    def decodeStatus44(self,statusBytes):
        # Wheel speed configuration
        self.status['WSpeedScale'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False) * WSSF2PPM
        if statusBytes[0:2] == b'\xFF\xFF': del self.status['WSpeedScale']

        self.status['WSpeedScaleStd'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False) * WSSFA2PC
        if statusBytes[2:4] == b'\xFF\xFF': del self.status['WSpeedScaleStd']

        self.status['OptionWSpeedDelay'] = statusBytes[4] * WSDELAY2S
        if statusBytes[4] == 0xFF: del self.status['OptionWSpeedDelay']

        self.status['OptionWSpeedZVDelay'] = statusBytes[5] * WSDELAY2S
        if statusBytes[5] == 0xFF: del self.status['OptionWSpeedZVDelay']

        self.status['OptionWSpeedNoiseStd'] = statusBytes[6] * WSNOISE2CNT
        if statusBytes[6] == 0xFF: del self.status['OptionWSpeedNoiseStd']


    def decodeStatus45(self,statusBytes):
        # Wheel speed counts
        self.status['WSpeedCount'] = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=False)
        
        try:
            m = self.status['GpsMinutes'] # May be invalid, hence 'try'
            s = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False) * 0.001
            self.status['WSpeedTime'] = GPS_STARTTIME + \
                datetime.timedelta( minutes=self.status['GpsMinutes'], seconds=self.nav['GpsSeconds'] )
            if statusBytes[4:6] == b'\xFF\xFF': del self.status['WSpeedTime']
        except:
            pass
        
        self.status['WSpeedTimeUnchanged'] = statusBytes[6] * WSDELAY2S
        if statusBytes[6] == 0xFF: del self.status['WSpeedTimeUnchanged']
        
        # todo: calculate tacho frequency - see OxTS NCom decoders


    def decodeStatus46(self,statusBytes):
        # Advanced whees speed lever arm
        self.status['WSpeedLeverArmX'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * WSPOS2M
        self.status['WSpeedLeverArmY'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * WSPOS2M
        self.status['WSpeedLeverArmZ'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * WSPOS2M
        if statusBytes[6] > 0:
            del self.status['WSpeedLeverArmX']
            del self.status['WSpeedLeverArmY']
            del self.status['WSpeedLeverArmZ']       


    def decodeStatus47(self,statusBytes):
        # Advanced wheel speed lever arm accuracy
        self.status['WSpeedLeverArmXAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * WSPOSA2M
        self.status['WSpeedLeverArmYAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * WSPOSA2M
        self.status['WSpeedLeverArmZAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * WSPOSA2M
        if statusBytes[6] > 0:
            del self.status['WSpeedLeverArmXAcc']
            del self.status['WSpeedLeverArmYAcc']
            del self.status['WSpeedLeverArmZAcc']       


    def decodeStatus48(self,statusBytes):
        # Undulation and dilution of precision of GPS
        self.status['Undulation'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * UNDUL2M
        if statusBytes[0:2] == b'\x00\x80': del self.status['Undulation']
        
        self.status['HDOP'] = statusBytes[2] * DOPFACTOR
        if statusBytes[2] == 0xFF: del self.status['HDOP']
        
        self.status['PDOP'] = statusBytes[3] * DOPFACTOR
        if statusBytes[3] == 0xFF: del self.status['PDOP']

        if statusBytes[2] != 0xFF and statusBytes[3] == 0xFF:
            x = max((self.status['PDOP']**2 - self.status['HDOP']**2,0.0))
            self.status['VDOP'] = x**0.5
        
        self.status['DatumEllipsoid'] = statusBytes[6]
        if statusBytes[6] == 0xFF: del self.status['DatumEllipsoid']
        
        self.status['DatumEarthFrame'] = statusBytes[7]
        if statusBytes[7] == 0xFF: del self.status['DatumEarthFrame']


    # todo: decodeStatus49: Omnistar
    
    
    def decodeStatus50(self,statusBytes):
        # Information sent to the command decoder (e.g. through UDP port 3001)
        self._updateLE16(int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False),'CmdChars')
        self._updateLE16(int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False),'CmdPkts')
        self._updateLE16(int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False),'CmdCharsSkipped')
        self._updateLE16(int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False),'CmdErrors')

    def decodeStatus51(self,statusBytes):
        # Additional slip point 1
        self.status['SlipPoint1X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint1Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint1Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint1X']
            del self.status['SlipPoint1Y']
            del self.status['SlipPoint1Z']       


    def decodeStatus52(self,statusBytes):
        # Additional slip point 2
        self.status['SlipPoint2X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint2Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint2Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint2X']
            del self.status['SlipPoint2Y']
            del self.status['SlipPoint2Z']       


    def decodeStatus53(self,statusBytes):
        # Additional slip point 3
        self.status['SlipPoint3X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint3Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint3Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint3X']
            del self.status['SlipPoint3Y']
            del self.status['SlipPoint3Z']       


    def decodeStatus54(self,statusBytes):
        # Additional slip point 4
        self.status['SlipPoint4X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint4Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint4Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint4X']
            del self.status['SlipPoint4Y']
            del self.status['SlipPoint4Z']       

    def decodeStatus55(self,statusBytes):
        # Status information about primary GNSS receiver
        self.status['GpsPrimaryAntStatus'] = statusBytes[0] & 0x03
        if (statusBytes[0] & 0x03) == 0x03: del self.status['GpsPrimaryAntStatus']
        
        self.status['GpsPrimaryAntPower'] = (statusBytes[0] & 0x0C) >> 2
        if (statusBytes[0] & 0x0C) == 0x0C: del self.status['GpsPrimaryAntPower']

        self.status['GpsPrimaryCpuUsed'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['GpsPrimaryCpuUsed']

        self.status['GpsPrimaryCoreNoise'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['GpsPrimaryCoreNoise']
                
        self.status['GpsPrimaryBaud'] = statusBytes[3]
        if statusBytes[3] == 0xFF: del self.status['GpsPrimaryBaud']
        
        self.status['GpsPrimaryNumSats'] = statusBytes[4]
        if statusBytes[4] == 0xFF: del self.status['GpsPrimaryNumSats']
        
        self.status['GpsPrimaryPosMode'] = statusBytes[5]
        if statusBytes[5] == 0xFF: del self.status['GpsPrimaryPosMode']
        
        self.status['GpsPrimaryCoreTemp'] = statusBytes[6] + TEMPK_OFFSET + ABSZERO_TEMPC
        if statusBytes[6] == 0xFF: del self.status['GpsPrimaryCoreTemp']
        
        self.status['GpsPrimarySupplyVolt'] = statusBytes[7] * SUPPLYV2V
        if statusBytes[7] == 0xFF: del self.status['GpsPrimarySupplyVolt']


    def decodeStatus56(self,statusBytes):
        # Status information about secondary GNSS receiver
        self.status['GpsSecondaryAntStatus'] = statusBytes[0] & 0x03
        if (statusBytes[0] & 0x03) == 0x03: del self.status['GpsSecondaryAntStatus']
        
        self.status['GpsSecondaryAntPower'] = (statusBytes[0] & 0x0C) >> 2
        if (statusBytes[0] & 0x0C) == 0x0C: del self.status['GpsSecondaryAntPower']

        self.status['GpsSecondaryCpuUsed'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['GpsSecondaryCpuUsed']

        self.status['GpsSecondaryCoreNoise'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['GpsSecondaryCoreNoise']
                
        self.status['GpsSecondaryBaud'] = statusBytes[3]
        if statusBytes[3] == 0xFF: del self.status['GpsSecondaryBaud']
        
        self.status['GpsSecondaryNumSats'] = statusBytes[4]
        if statusBytes[4] == 0xFF: del self.status['GpsSecondaryNumSats']
        
        self.status['GpsSecondaryPosMode'] = statusBytes[5]
        if statusBytes[5] == 0xFF: del self.status['GpsSecondaryPosMode']
        
        self.status['GpsSecondaryCoreTemp'] = statusBytes[6] + TEMPK_OFFSET + ABSZERO_TEMPC
        if statusBytes[6] == 0xFF: del self.status['GpsSecondaryCoreTemp']
        
        self.status['GpsSecondarySupplyVolt'] = statusBytes[7] * SUPPLYV2V
        if statusBytes[7] == 0xFF: del self.status['GpsSecondarySupplyVolt']

    def decodeStatus57(self,statusBytes):
        # Position estimate of primary GPS antenna lever-arm (extended range)
        sf = statusBytes[7]        
        self.status['GAPx'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSPOS2M * sf
        self.status['GAPy'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSPOS2M * sf
        self.status['GAPz'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GPSPOS2M * sf
        if statusBytes[6] > 150 or statusBytes[7] == 0:
            del self.status['GAPx']
            del self.status['GAPy']
            del self.status['GAPz']       


    def decodeStatus58(self,statusBytes):
        # vehicle to output rotation - very rarely used and not in config software
        self.status['OpHeading'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['OpPitch'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['OpRoll'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['OpHeading']
            del self.status['OpPitch']
            del self.status['OpRoll']       


    def decodeStatus59(self,statusBytes):
        # IMU decoding status
        self._updateLE16(int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False),'ImuMissedPkts')
        self._updateLE8(statusBytes[2],'ImuResetCount')
        self._updateLE8(statusBytes[3],'ImuErrorCount')


    def decodeStatus60(self,statusBytes):
        # Definition of the surface angles
        self.status['Ned2SurfHeading'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['Ned2SurfPitch'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        self.status['Ned2SurfRoll'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * GPSATT2RAD * RAD2DEG
        if statusBytes[6] > 150:
            del self.status['Ned2SurfHeading']
            del self.status['Ned2SurfPitch']
            del self.status['Ned2SurfRoll']       


    def decodeStatus61(self,statusBytes):
        # Internal information about external GNSS receiver
        self._updateLE16(int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=False),'GpsExternalChars')
        self._updateLE16(int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=False),'GpsExternalPkts')
        self._updateLE16(int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False),'GpsExternalCharsSkipped')
        self._updateLE16(int.from_bytes(statusBytes[6:8], byteorder = 'little', signed=False),'GpsExternalOldPkts')


    def decodeStatus62(self,statusBytes):
        # Status information about external GNSS receiver
        self.status['GpsExternalAntStatus'] = statusBytes[0] & 0x03
        if (statusBytes[0] & 0x03) == 0x03: del self.status['GpsExternalAntStatus']
        
        self.status['GpsExternalAntPower'] = (statusBytes[0] & 0x0C) >> 2
        if (statusBytes[0] & 0x0C) == 0x0C: del self.status['GpsExternalAntPower']

        self.status['GpsExternalCpuUsed'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['GpsExternalCpuUsed']

        self.status['GpsExternalCoreNoise'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['GpsExternalCoreNoise']
                
        self.status['GpsExternalBaud'] = statusBytes[3]
        if statusBytes[3] == 0xFF: del self.status['GpsExternalBaud']
        
        self.status['GpsExternalNumSats'] = statusBytes[4]
        if statusBytes[4] == 0xFF: del self.status['GpsExternalNumSats']
        
        self.status['GpsExternalPosMode'] = statusBytes[5]
        if statusBytes[5] == 0xFF: del self.status['GpsExternalPosMode']
        
        self.status['GpsExternalCoreTemp'] = statusBytes[6] + TEMPK_OFFSET + ABSZERO_TEMPC
        if statusBytes[6] == 0xFF: del self.status['GpsExternalCoreTemp']
        
        self.status['GpsExternalSupplyVolt'] = statusBytes[7] * SUPPLYV2V
        if statusBytes[7] == 0xFF: del self.status['GpsExternalSupplyVolt']

    # decodeStatus63: todo: angular acceleration low-pass filter

    def decodeStatus64(self,statusBytes):
        # Hardware information and GPS receiver configurations
        self.status['CpuPcbType'] = statusBytes[0]
        if statusBytes[0] == 0xFF: del self.status['CpuPcbType']

        self.status['GpsSetType'] = statusBytes[1]
        if statusBytes[1] == 0xFF: del self.status['GpsSetType']

        self.status['GpsSetFormat'] = statusBytes[2]
        if statusBytes[2] == 0xFF: del self.status['GpsSetFormat']
        
        self.status['DualPortRamStatus'] = statusBytes[3]
        if statusBytes[3] == 0xFF: del self.status['DualPortRamStatus']
        
        self.status['GpsPrimarySetPosRate'] = statusBytes[4] & 0x0F
        if statusBytes[4]&0x0F == 0x0F: del self.status['GpsPrimarySetPosRate']
        
        self.status['GpsPrimarySetVelRate'] = (statusBytes[4]>>4) & 0x0F
        if (statusBytes[4]>>4)&0x0F == 0x0F: del self.status['GpsPrimarySetVelRate']

        self.status['GpsPrimarySetRawRate'] = statusBytes[5] & 0x0F
        if statusBytes[5]&0x0F == 0x0F: del self.status['GpsPrimarySetRawRate']

        self.status['GpsSecondarySetRawRate'] = (statusBytes[5]>>4) & 0x0F
        if (statusBytes[5]>>4)&0x0F == 0x0F: del self.status['GpsSecondarySetRawRate']

        gf = ~statusBytes[6]
        self.status['GnssGlonassEnabled'] = (gf & 0x01) > 0
        self.status['GnssGalileoEnabled'] = (gf & 0x02) > 0
        self.status['GnssRawRngEnabled'] = (gf & 0x04) > 0
        self.status['GnssRawDopEnabled']  = (gf & 0x08) > 0
        self.status['GnssRawL1Enabled']  = (gf & 0x10) > 0
        self.status['GnssRawL2Enabled']  = (gf & 0x20) > 0
        self.status['GnssRawL5Enabled']  = (gf & 0x40) > 0
        if (gf & 0x80) == 0:
            del self.status['GnssGlonassEnabled']
            del self.status['GnssGalileoEnabled']
            del self.status['GnssRawRngEnabled']
            del self.status['GnssRawDopEnabled']
            del self.status['GnssRawL1Enabled']
            del self.status['GnssRawL2Enabled']
            del self.status['GnssRawL5Enabled']


    def decodeStatus65(self,statusBytes):
        # Camera 1 out event timing
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Digital1OutTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Digital1OutTime']
        
        self.status['Digital1OutCount'] = statusBytes[7]


    def decodeStatus66(self,statusBytes):
        # Extended local co-ordinate/reference frame for latitude and longitude
        self.status['RefFrameLat'] = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True) * FINEANG2RAD * RAD2DEG
        if statusBytes[0:4] == b'\x00\x00\x00\x80': del self.status['RefFrameLat']
        
        self.status['RefFrameLon'] = int.from_bytes(statusBytes[4:8], byteorder = 'little', signed=True) * FINEANG2RAD * RAD2DEG
        if statusBytes[4:8] == b'\x00\x00\x00\x80': del self.status['RefFrameLon']
        self.computeRefFrame()


    def decodeStatus67(self,statusBytes):
        # Extended local co-ordinate/reference frame for altitude and heading
        self.status['RefFrameAlt'] = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True) * ALT2M
        if statusBytes[0:4] == b'\x00\x00\x00\x80': del self.status['RefFrameAlt']
        
        self.status['RefFrameHeading'] = int.from_bytes(statusBytes[4:8], byteorder = 'little', signed=True) * FINEANG2RAD * RAD2DEG
        if statusBytes[4:8] == b'\x00\x00\x00\x80': del self.status['RefFrameHeading']
        self.computeRefFrame()


    def computeRefFrame(self):
        # Compute reference frame if all the information needed is available
        # Note that, if the reference frame changes then there will be a glitch
        # because the reference frame lat/lon won't match the refernce frame alt/heading
        # Not sure how to avoid this. Should go away quite quickly when both are updated.
        if 'RefFrameLat' in self.status \
        and 'RefFrameLon' in self.status \
        and 'RefFrameAlt' in self.status \
        and 'RefFrameHeading' in self.status:
            # Compute the local reference frame constants
            # These are used to compute LocalX, LocalY, etc. in self.nav
            tmp = EARTH_ECCENTRICITY * math.sin(self.status['RefFrameLat']*DEG2RAD)
            tmp = 1.0 - tmp * tmp
            sqt = math.sqrt(tmp)
            # These are the earth radii
            rho_e = EARTH_EQUAT_RADIUS * (1.0 - EARTH_ECCENTRICITY * EARTH_ECCENTRICITY) / (sqt * tmp)
            rho_n = EARTH_EQUAT_RADIUS / sqt
            # Set the Ref...Radius in units of m/degree
            self.status['RefLatRadius'] = (rho_e + self.status['RefFrameAlt']) * DEG2RAD
            self.status['RefLonRadius'] = (rho_n + self.status['RefFrameAlt']) * math.cos(self.status['RefFrameLat'] * DEG2RAD) * DEG2RAD
            # For easier rotation from Northing/Easting to XY
            self.status['RefHeadingCos'] = math.cos(self.status['RefFrameHeading'] * DEG2RAD)
            self.status['RefHeadingSin'] = math.sin(self.status['RefFrameHeading'] * DEG2RAD)
        else:
            # Remove any computed values
            try:
                del self.status['RefLatRadius']
                del self.status['RefLonRadius']
                del self.status['RefHeadingCos']
                del self.status['RefHeadingSin']
            except:
                pass

    def decodeStatus68(self,statusBytes):
        # Additional slip point 5
        self.status['SlipPoint5X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint5Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint5Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint5X']
            del self.status['SlipPoint5Y']
            del self.status['SlipPoint5Z']       


    def decodeStatus69(self,statusBytes):
        # Additional slip point 6
        self.status['SlipPoint6X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint6Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint6Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint6X']
            del self.status['SlipPoint6Y']
            del self.status['SlipPoint6Z']       


    def decodeStatus70(self,statusBytes):
        # Additional slip point 7
        self.status['SlipPoint7X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint7Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint7Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint7X']
            del self.status['SlipPoint7Y']
            del self.status['SlipPoint7Z']       


    def decodeStatus71(self,statusBytes):
        # Additional slip point 8
        self.status['SlipPoint8X'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint8Y'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * SP2M
        self.status['SlipPoint8Z'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * SP2M
        if statusBytes[6] > 0:
            del self.status['SlipPoint8X']
            del self.status['SlipPoint8Y']
            del self.status['SlipPoint8Z']       


    def decodeStatus72(self,statusBytes):
        # Accelerometer scale factor
        self.status['AxSf'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * ASFACTOR
        self.status['AySf'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * ASFACTOR
        self.status['AzSf'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * ASFACTOR
        if statusBytes[6] > 150:
            del self.status['AxSf']
            del self.status['AySf']
            del self.status['AzSf']       


    def decodeStatus73(self,statusBytes):
        # Accelerometer scale factor accuracy
        self.status['AxSfAcc'] = int.from_bytes(statusBytes[0:2], byteorder = 'little', signed=True) * ASAFACTOR
        self.status['AySfAcc'] = int.from_bytes(statusBytes[2:4], byteorder = 'little', signed=True) * ASAFACTOR
        self.status['AzSfAcc'] = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=True) * ASAFACTOR
        if statusBytes[6] > 150:
            del self.status['AxSfAcc']
            del self.status['AySfAcc']
            del self.status['AzSfAcc']       

    # decodeStatus74 todo: low pass filter for accelerometers


    def decodeStatus79(self,statusBytes):
        # Trigger 1 output event timings (falling edge triggers)
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Trig2FallingTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Trig2FallingTime']
        
        self.status['Trig2FallingCount'] = statusBytes[7]


    def decodeStatus80(self,statusBytes):
        # Trigger 2 output event timing (rising edge triggers)
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Trig2RisingTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Trig2RisingTime']
        
        self.status['Trig2RisingCount'] = statusBytes[7]


    def decodeStatus81(self,statusBytes):
        # Camera 2 out event timing
        m = int.from_bytes(statusBytes[0:4], byteorder = 'little', signed=True)
        ms = int.from_bytes(statusBytes[4:6], byteorder = 'little', signed=False)
        us = statusBytes[6]
        self.status['Digital2OutTime'] = m * 60.0 + ms * 0.001 + us * FINETIME2SEC
        if m == 0: del self.status['Digital2OutTime']
        
        self.status['Digital2OutCount'] = statusBytes[7]


