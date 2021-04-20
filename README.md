# GNSSBaseStation

### Low-cost GNSS RTK Base Station
The device is permanently operating to support the fleet of RTK rovers of local forestry company since November, 2020. The prototype is fully functioning with proven ±1 centimeter RTK precision.

### Hardware
- [Raspberry Pi] microcomputer
- uBlox [GNSS chip]
- [Zero2Go] power supply module
- [UPS module]
- 3G modem module for autonomous internet access

### Software
- Python app (runs under Raspbian Buster)
- RTKLIB library
- UBX library
- Zero2Go integration
- [web interface] for configuration (Django backend + frontend)
- separate watchdog process for automatic recovery after possible software failures

See also the [photo album of the prototype](https://photos.app.goo.gl/sFVDawy2RFc2KMGJ9)

[Raspberry Pi]: https://www.raspberrypi.org/products/raspberry-pi-3-model-b "Famous single-board microcomputer for prototyping"
[GNSS chip]: https://www.u-blox.com/en/product/zed-f9p-module "uBlox ZED-F9P GNSS module"
[Zero2Go]: http://www.uugear.com/product/zero2go "Power supply module for Raspberry Pi"
[UPS module]: https://img.joomcdn.net/ca7776a690a82edaaa1614e4d83237471649e7e2_original.jpeg "Backup Li-ion battery + voltage converter"
[web interface]: https://drive.google.com/file/d/1GasgsTXRUagl4gKymb2i66jQ8qQs3EHE/view?usp=sharing "Screenshot of the web-based configuration UI"
