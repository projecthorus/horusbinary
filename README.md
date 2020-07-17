# Project Horus's MFSK Binary Telemetry System

![Horus Binary Modem FFT](https://github.com/projecthorus/horusbinary/raw/master/doc/modem_fft.jpg)
Above: Spectrogram of the Horus Binary modem signal.

Please refer to the [wiki pages](https://github.com/projecthorus/horusbinary/wiki) for the latest version of this documentation.

**IMPORTANT NOTE: This repository is being transitioned across to [horusdemodlib](https://github.com/projecthorus/horusdemodlib). The decoders in this repository will remain compatible with the decoders in horusdemodlib, at least for the Horus Binary v1 mode.**

## What is it?
This repository contains a demodulator and helper scripts for the 'Horus Binary' Multiple-Frequency-Shift-Keying (MFSK) modem, which was specifically designed to provide high reliability telemetry from High-Altitude Balloon (HAB) payloads. 

[Project Horus](https://www.areg.org.au/archives/category/activities/project-horus) HAB flights use this modem as their primary tracking telemetry, usually transmitting on 434.660 MHz.

The FSK demodulator that forms the core of this modem was developed by [David Rowe](http://rowetel.com) as part of the [codec2](https://github.com/drowe67/codec2) project. This modem has also been integrated into David's [FreeDV](https://freedv.org/) application as of version 1.4. 

Along with the modem are some helper scripts written by [Mark Jessop](https://rfhead.net), which decode the binary data, and upload telemetry to the [Habitat](http://habitat.habhub.org/) HAB tracking database, for display on the [HabHub Tracker](https://tracker.habhub.org/) map.

## Why use it?
A HAB telemetry payload transmitting Horus Binary format telemetry can provide position updates approximately every 3 seconds. Using just 10mW transmit power on the 434 MHz [ISM](https://en.wikipedia.org/wiki/ISM_band)/[LIPD](https://www.acma.gov.au/licences/low-interference-potential-devices-lipd-class-licence)/70cm band, this modem can offer ~7dB improved demodulation performance compared to [RTTY](https://en.wikipedia.org/wiki/Radioteletype) running at the same baud rate. There is some further information on the modem performance [available here](https://www.rowetel.com/?p=5906).

This means potentially longer decoding range, both in the air, and on the ground. The modem uses rate r=1/2 [Golay](https://en.wikipedia.org/wiki/Binary_Golay_code) forward-error correction, so you'll have far less issues with failed packet decodes.

The ye-olde RTTY transmitters used by many high-altitude balloon flights encode telemetry as ASCII text. This is very wasteful compared to just sending data as raw binary types. RTTY also uses [RS232](https://en.wikipedia.org/wiki/RS-232) framing, which means even more overhead. Horus Binary uses a binary packet format, which gets the basic tracking data across in just 22 bytes. Some information on the packet and framing format is [available here](https://github.com/projecthorus/horusbinary/wiki/2---Modem-Details).

The current Horus Binary modem uses ~1kHz of bandwidth, so can be received using conventional single-sideband receivers, just like you would do with a RTTY payload. Software-Defined Radio receivers can also be used.

## How do I receive it?
So, you want to receive telemetry from someone's high-altitude balloon flight, or set up to receive telemetry from your own payload?

First up, you will need some kind of receiver for whatever frequency the telemetry is being transmitted on. Usually this is within the 434 MHz ISM/LIPD/70cm band, but could be different. 
You need a receiver capable of receiving [Single-Sideband](https://en.wikipedia.org/wiki/Single-sideband_modulation), in particular the 'upper' sideband ('USB' - no, not that [USB](https://en.wikipedia.org/wiki/Universal_serial_bus)). 
This could be a conventional amateur radio transceiver (think IC-7000, IC-706, FT-817, the list goes on and on...), or a scanner (Icom IC-R10, Yupiteru MVT-7100, etc...).

You can also use software-defined radio receivers, such as the ubiquitous [RTL-SDR](https://www.rtl-sdr.com/buy-rtl-sdr-dvb-t-dongles/) (amongst others), along with software such as [SDR-Console](https://www.sdr-radio.com/console), [SDR#](https://airspy.com/download/), or [GQRX](http://gqrx.dk/).

### Windows
Running Windows? It's easiest to demodulate telemetry using the FreeDV GUI. [Use this setup guide.](https://github.com/projecthorus/horusbinary/wiki/1.1---RX-Guide-Using-FreeDV)

### Linux / OSX
The FreeDV guide linked above is also applicable to Linux & OSX. 

However, if you want to receive using a SDR, then follow the [GQRX reception guide](https://github.com/projecthorus/horusbinary/wiki/1.2---RX-Guide-using-GQRX-(Linux-and-OSX)).

### Raspberry Pi 'Headless' Setup
It's also possible to make a 'headless' (no screen) receiver using a RTL-SDR and a Raspberry Pi (or some other small Linux machine). Follow [this guide](https://github.com/projecthorus/horusbinary/wiki/1.3---Raspberry-Pi-'Headless'-RX-Guide).

## General Info
There is also some general information about running the modem from the command-line [available here](https://github.com/projecthorus/horusbinary/wiki/2---Modem-Details#usage---horus-demod).

## How do I transmit it?
Currently the 'reference platform' for Horus Binary telemetry transmission is the Vaisala RS41 radiosonde. Using [radiosonde_auto_rx](https://github.com/projecthorus/radiosonde_auto_rx) we track and recover these radiosonde and reprogram them with [our own open source firmware](https://github.com/darksidelemm/RS41HUP), which generates the Horus Binary modulation. 
These radiosondes are launched in many places around the world, so go hunting and get your own free balloon tracker!

**If you are going to fly your own payload using Horus Binary, you must get a payload ID allocated for your use. This can be done by submitting an issue or a pull request to this repository, or e-mailing me at vk5qi (at) rfhead.net**

You will also need to set up a [Habitat Payload Document](https://github.com/projecthorus/horusbinary/wiki/3-Setting-up-a-Habitat-Payload-Document), so that the payload telemetry appears on the tracker.

There is also some older code targeting an ATMega328 + Radiometrix MTX2 [available here](https://github.com/darksidelemm/uAvaNutBinary/tree/master/uAvaNutBinary), however this code has not been used in a long time. 

I intend to produce implementations for other common transmitters, such as the RFM98W, which should also be capable of much higher order MFSK modulations, improving performance even more!

## Contacts
* [Mark Jessop](https://github.com/darksidelemm) - vk5qi@rfhead.net
* [David Rowe](https://rowetel.com) - david@rowetel.com
