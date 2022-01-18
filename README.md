# ncom-web-gad
This branch, ncom-web-gad, is a version of ncom-web that can be used to explore how generic aiding works with an OxTS inertial navigation system.

ncom-web is a python program that receives NCOM data from OxTS INSs (RT3000, xNAV, etc.) and makes the real-time data available on web pages. You can view the web page on a PC, tablet or phone. See the main branch of the repository for instructions.

# Generic aiding

Generic aiding is OxTS's term for updating the Kalman filter with external measurements. For example, generic aiding can be used to provide position measurements from an indoor positioning system. Using generic aiding, GNSS does not need to be the only means of keeping the inertial navigation system accurate.

Generic aiding uses OxTS's generic aiding SDK, see [https://github.com/OxfordTechnicalSolutions/gad-sdk](https://github.com/OxfordTechnicalSolutions/gad-sdk). It also requires the generic aiding feature codes, which you can get from support@oxts.com.

Generic aiding includes several different types of measurement input. This example shows position, velocity and attitude (angles) updates. For example, the code can send fixed positions at about 2Hz.

# Instructions

Follow these steps to get generic aiding to work on your OxTS inertial navigation system:

* Set up your OxTS inertial navigation system using the default settings but with the following changes:
  - Dual antenna heading changed from 180 degrees to 0 degrees
  - _-time_sync_int_ added as an advanced command
  - (A copy of the configuration I used is in folder xnav-config)
* Set the IP address, if needed. It must be on the same network as your computer.
* Install python 3 (I was using 3.9.2 on Raspberry Pi Os)
* Download this branch of the repository
* Run **python main.py**
* Go to web page http://<ip address>:8000 _(where <ip address> is the ip address of your computer)_
* Find the IP address of your OxTS inertial navigation system
* Click on the gad page
