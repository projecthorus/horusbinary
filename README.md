# Project Horus's Binary Telemetry Utilities
These scripts are intended to be used alongside the horus FSK/RTTY decoder from [codec2-dev](https://svn.code.sf.net/p/freetel/code/codec2-dev).

* `horusbinary.py` - Decode binary/RTTY telemetry received via stdin, and send to Habitat & [OziMux](https://github.com/projecthorus/horus_utils/wiki#data-selection---ozimux).

## Dependencies
* TODO: horus_api CLI utility compilation instructions here.

## Example Usage
* TODO: Example usage.
* `nc -l -u localhost 7355 | ./horus_api | python horusbinary.py MYCALL`