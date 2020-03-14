from pathlib import Path

from serial import Serial
import sys

PROJECT = Path('/home/pi/app')
LOG = PROJECT / 'logs' / 'input_proxy.log'

PREAMB = b'\xD3'
RTCM1008 = b'\xD3\x00\x06\x3F\x00\x00\x00\x00\x00\x99\x25\xCA'

try:
    send = sys.stdout.buffer.write
    flush = sys.stdout.buffer.flush

    with Serial('/dev/serial0', baudrate=115200) as dev:
        while True:
            while dev.read(len(PREAMB)) != PREAMB: pass
            datalen = dev.read(2)
            data = dev.read(int.from_bytes(datalen, 'big', signed=False))
            crc24 = dev.read(3)

            msgid = int.from_bytes(data[:2], 'big', signed=False) >> 4

            send(PREAMB+datalen+data+crc24)
            flush()

            if msgid == 1005:
                send(RTCM1008)
                flush()

except Exception as e:
    LOG.write_text(str(e))
    exit(1)
