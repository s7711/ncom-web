# ncom-web-gad
This branch, ncom-web-gad, is a version of ncom-web that can be used to explore how generic aiding works with an OxTS inertial navigation system.

ncom-web is a python program that receives NCOM data from OxTS INSs (RT3000, xNAV, etc.) and makes the real-time data available on web pages. You can view the web page on a PC, tablet or phone. See the main branch of the repository for instructions.

# Generic aiding

Generic aiding is OxTS's term for updating the Kalman filter with external measurements. For example, generic aiding can be used to provide position measurements from an indoor positioning system. Using generic aiding, GNSS does not need to be the only means of keeping the inertial navigation system accurate.

Generic aiding uses OxTS's generic aiding SDK, see [https://github.com/OxfordTechnicalSolutions/gad-sdk](https://github.com/OxfordTechnicalSolutions/gad-sdk). It also requires the generic aiding feature codes, which you can get from support@oxts.com.

Generic aiding includes several different types of measurement input. This example shows position, velocity and attitude (angles) updates. For example, the code can send fixed positions at about 2Hz.

# Instructions

Follow these steps to get generic aiding to work on your OxTS inertial navigation (INS) system:

* For these instructions the INS should not have a GNSS antenna connected
* Set up your INS using the default settings but with the following changes:
  - Dual antenna heading changed from 180 degrees to 0 degrees
  - _-time_sync_int_ added as an advanced command
  - (A copy of the configuration I used is in folder xnav-config)
* Set the IP address, if needed. It must be on the same network as your computer.
* Install python 3 (I was using 3.9.2 on Raspberry Pi Os)
* Download this branch of the repository
* Run **python main.py**
* Go to web page http://\<ip address\>:8000 _(where \<ip address\> is the ip address of your computer)_
* Find the IP address of your INS
* Click on the GAD page

For generic aiding work we need to initialise the INS at roughly the correct place and with roughly the correct heading.

* In the "Send" box at the top enter _base \<Lat\> \<Lon\> \<Alt\>_ where _\<Lat\>_ is your latitude in degrees, _\<Lon\>_ is your longitude in degrees and _\<Alt\>_ is your altitude in metres. OxTS generally outputs the elipsodial altitude, so this is the altitude you should use.
* In the "Send" box enter _!set time 2000 1234_ where _2000_ is the GPS week and _1234_ is the number of seconds into the GPS week. These do not need to be exact and using "!set time 2000 1234" will work and the INS will report a time in 6th June 2018. The GpsTime field should show the time.
* Click on _Position A_. The "GNSS Position Mode" at the bottom of the page should show 34.
* Enter _!set init aidpos \<Lat\> \<Lon\> \<Alt\>_ with the same latitude, longtitude and altitude as before.
* Enter _!set init aidvel 0 0 0_ to set the initial velocity to zero.
* Enter _!set init hea \<heading\>_ where _\<heading\>_ is the approximate heading of the INS.

The INS should initialise. The Speed box should show the current speed (about zero), the Heading box should show the current heading. The XY grid will show the approximate position in metres, compared to the base latitude and longitude entered originally.

The following options are available:

* Click _Position Stop_ to stop sending position updates. The position should start to drift.
* Click on _Position A_ to start sending position updates for the base latitude and longitude again
* Click on _ZVU_ to start sending zero velocity updates, and _ZVU Stop_ to stop.
* Click on _Position B_ to start sending position updates for a position that is about 50 cm west of the base position.
* Click on _Position C_ to start sending position updates for a position that is about 40 cm north of the base position.
* Click on _Position D_ to start sending position updates for a position that is about 50 cm west and 40 cm north of the base position.
* Enter _att \<heading\> \<pitch\> \<roll\>_ (for example "att 90 0 0") to start sending attitude updates and _att stop_ to stop sending attitude updates. (No user interface button is provided).

