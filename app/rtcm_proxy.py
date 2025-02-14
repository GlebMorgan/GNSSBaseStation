#!/usr/bin/env python3
import sys
from argparse import ArgumentParser
from itertools import count
from pathlib import Path

from serial import Serial


crc24table = (
    0x000000, 0x864CFB, 0x8AD50D, 0x0C99F6, 0x93E6E1, 0x15AA1A, 0x1933EC, 0x9F7F17,
    0xA18139, 0x27CDC2, 0x2B5434, 0xAD18CF, 0x3267D8, 0xB42B23, 0xB8B2D5, 0x3EFE2E,
    0xC54E89, 0x430272, 0x4F9B84, 0xC9D77F, 0x56A868, 0xD0E493, 0xDC7D65, 0x5A319E,
    0x64CFB0, 0xE2834B, 0xEE1ABD, 0x685646, 0xF72951, 0x7165AA, 0x7DFC5C, 0xFBB0A7,
    0x0CD1E9, 0x8A9D12, 0x8604E4, 0x00481F, 0x9F3708, 0x197BF3, 0x15E205, 0x93AEFE,
    0xAD50D0, 0x2B1C2B, 0x2785DD, 0xA1C926, 0x3EB631, 0xB8FACA, 0xB4633C, 0x322FC7,
    0xC99F60, 0x4FD39B, 0x434A6D, 0xC50696, 0x5A7981, 0xDC357A, 0xD0AC8C, 0x56E077,
    0x681E59, 0xEE52A2, 0xE2CB54, 0x6487AF, 0xFBF8B8, 0x7DB443, 0x712DB5, 0xF7614E,
    0x19A3D2, 0x9FEF29, 0x9376DF, 0x153A24, 0x8A4533, 0x0C09C8, 0x00903E, 0x86DCC5,
    0xB822EB, 0x3E6E10, 0x32F7E6, 0xB4BB1D, 0x2BC40A, 0xAD88F1, 0xA11107, 0x275DFC,
    0xDCED5B, 0x5AA1A0, 0x563856, 0xD074AD, 0x4F0BBA, 0xC94741, 0xC5DEB7, 0x43924C,
    0x7D6C62, 0xFB2099, 0xF7B96F, 0x71F594, 0xEE8A83, 0x68C678, 0x645F8E, 0xE21375,
    0x15723B, 0x933EC0, 0x9FA736, 0x19EBCD, 0x8694DA, 0x00D821, 0x0C41D7, 0x8A0D2C,
    0xB4F302, 0x32BFF9, 0x3E260F, 0xB86AF4, 0x2715E3, 0xA15918, 0xADC0EE, 0x2B8C15,
    0xD03CB2, 0x567049, 0x5AE9BF, 0xDCA544, 0x43DA53, 0xC596A8, 0xC90F5E, 0x4F43A5,
    0x71BD8B, 0xF7F170, 0xFB6886, 0x7D247D, 0xE25B6A, 0x641791, 0x688E67, 0xEEC29C,
    0x3347A4, 0xB50B5F, 0xB992A9, 0x3FDE52, 0xA0A145, 0x26EDBE, 0x2A7448, 0xAC38B3,
    0x92C69D, 0x148A66, 0x181390, 0x9E5F6B, 0x01207C, 0x876C87, 0x8BF571, 0x0DB98A,
    0xF6092D, 0x7045D6, 0x7CDC20, 0xFA90DB, 0x65EFCC, 0xE3A337, 0xEF3AC1, 0x69763A,
    0x578814, 0xD1C4EF, 0xDD5D19, 0x5B11E2, 0xC46EF5, 0x42220E, 0x4EBBF8, 0xC8F703,
    0x3F964D, 0xB9DAB6, 0xB54340, 0x330FBB, 0xAC70AC, 0x2A3C57, 0x26A5A1, 0xA0E95A,
    0x9E1774, 0x185B8F, 0x14C279, 0x928E82, 0x0DF195, 0x8BBD6E, 0x872498, 0x016863,
    0xFAD8C4, 0x7C943F, 0x700DC9, 0xF64132, 0x693E25, 0xEF72DE, 0xE3EB28, 0x65A7D3,
    0x5B59FD, 0xDD1506, 0xD18CF0, 0x57C00B, 0xC8BF1C, 0x4EF3E7, 0x426A11, 0xC426EA,
    0x2AE476, 0xACA88D, 0xA0317B, 0x267D80, 0xB90297, 0x3F4E6C, 0x33D79A, 0xB59B61,
    0x8B654F, 0x0D29B4, 0x01B042, 0x87FCB9, 0x1883AE, 0x9ECF55, 0x9256A3, 0x141A58,
    0xEFAAFF, 0x69E604, 0x657FF2, 0xE33309, 0x7C4C1E, 0xFA00E5, 0xF69913, 0x70D5E8,
    0x4E2BC6, 0xC8673D, 0xC4FECB, 0x42B230, 0xDDCD27, 0x5B81DC, 0x57182A, 0xD154D1,
    0x26359F, 0xA07964, 0xACE092, 0x2AAC69, 0xB5D37E, 0x339F85, 0x3F0673, 0xB94A88,
    0x87B4A6, 0x01F85D, 0x0D61AB, 0x8B2D50, 0x145247, 0x921EBC, 0x9E874A, 0x18CBB1,
    0xE37B16, 0x6537ED, 0x69AE1B, 0xEFE2E0, 0x709DF7, 0xF6D10C, 0xFA48FA, 0x7C0401,
    0x42FA2F, 0xC4B6D4, 0xC82F22, 0x4E63D9, 0xD11CCE, 0x575035, 0x5BC9C3, 0xDD8538,
)


def crc24(data: bytes) -> bytes:
    crc = 0
    for byte in data:
        crc = crc24table[(crc >> 16 ^ byte) & 0xFF] ^ (crc << 8)
    return (crc & 0xFFFFFF).to_bytes(3, 'big')


PREAMB = b'\xD3'

RTCM = {
    '1006': None,  # generated dynamically
    '1008_empty': b'\xD3\x00\x06\x3F\x00\x00\x00\x00\x00\x99\x25\xCA',
    '1008': b'\xD3\x00\x14\x3F\x00\x00\x0EGPPNULLANTENNA\x00\x00\x72\xD4\xE7',
    '1033': b'\xD3\x00\x24\x40\x90\x00\x0EGPPNULLANTENNA\x00\x00\x0DUBLOX ZED-F9P\x00\x00\x7D\x50\xA0',
}


def genRTCM1006(rtcm1005data: bytes) -> bytes:
    first_3_bytes = ((int.from_bytes(rtcm1005data[:2], 'big') & 0x000F) | (1006 << 4)).to_bytes(2, 'big')
    new_len = (len(rtcm1005data) + 2).to_bytes(2, 'big')
    new_data = PREAMB + new_len + first_3_bytes + rtcm1005data[2:] + b'\x00\x00'
    return new_data + crc24(new_data)


parser = ArgumentParser(description='RTCM3 stream proxy')

parser.add_argument('-in', '--input-stream',
                    dest='input', metavar='INPUT_STREAM',
                    help="input RTCM stream (default: <stdin>). "
                         "Supported stream formats: "
                         "serial://port:baudrate:bytesize:parity:stopbits, "
                         "file://filepath")

parser.add_argument('-out', '--output-stream',
                    dest='output', metavar='OUTPUT_STREAM',
                    help="output RTCM stream (default: <stdout>). "
                         "Supported stream format: file://filepath")

parser.add_argument('-a', '--anchor', required=True, dest='anchor', type=int,
                    help="RTCM message ID that would be searched in input stream "
                         "and serve as a trigger for injecting specified RTCM messages")

parser.add_argument('-m', '--messages', nargs='+', default=[], dest='msgs', metavar='MSG',
                    help="RTCM message IDs to inject after 'anchor' message")

parser.add_argument('-i', '--interval', default=1, dest='interval', type=int,
                    help="interval for injected messages relative to anchor. "
                         "Specified messages will be injected after every N-th "
                         "anchor message occurrence (default: %(default)s)")

parser.add_argument('-l', '--log-file', dest='log', type=Path,
                    help="file path for error output")


try:
    args = parser.parse_args()

    argument = 'argument -in/--input-stream'
    if args.input is None:
        source = sys.stdin.buffer
    else:
        try:
            stream_type, raw_config = args.input.split('://', maxsplit=1)
        except ValueError:
            parser.error(f"{argument}: invalid format: '{args.input}'")
        if stream_type == 'serial':
            serial_options = 'port', 'baudrate', 'bytesize', 'parity', 'stopbits'
            serial_params = (int(par) if par.isdecimal() else par for par in raw_config.split(':'))
            config = dict(zip(serial_options, serial_params))
            if not config['port'].startswith('/dev/'):
                config['port'] = f'/dev/{config["port"]}'
            try:
                source = Serial(**config)
            except ValueError as e:
                parser.error(f"{argument}: invalid serial options format: {e.args[0] or stream_type(e)}")
        elif stream_type == 'file':  # not tested
            try:
                source = open(raw_config, 'rb')
            except FileNotFoundError as e:
                parser.error(f"{argument}: {e}")
        else:
            parser.error(f"{argument}: unsupported input format: {stream_type}")

    argument = 'argument -out/--output-stream'
    if args.output is None:
        output = sys.stdout.buffer
    else:
        try:
            stream_type, filepath = args.output.split('://', maxsplit=1)
        except ValueError:
            parser.error(f"{argument}: invalid format: '{args.output}'")
        if stream_type == 'file':
            file = Path(filepath).absolute()
            if not file.exists():
                parser.error(f"{argument}: file {file} does not exist")
            output = file.open('wb')
        else:
            parser.error(f"{argument}: unsupported input format: {stream_type}")

    argument = 'argument -m/--messages'
    if any(msg not in RTCM for msg in args.msgs):
        parser.error(f"{argument}: encountered unsupported RTCM message id: {e}")

    argument = 'argument -l/--log-file'
    logfile = args.log.expanduser().resolve()
    if not logfile.parent.is_dir():
        parser.error(f"{argument}: invalid path: '{args.log}'")

    # Clear logfile from previous output if its size is not zero
    if logfile.stat().st_size != 0:
        logfile.write_text('')

    msgs = args.msgs
    send = output.write
    flush = output.flush
    anchor = args.anchor
    interval = args.interval

    with source, output:
        for i in count():
            while source.read(len(PREAMB)) != PREAMB: pass
            datalen = source.read(2)
            data = source.read(int.from_bytes(datalen, 'big', signed=False))
            crc = source.read(3)

            msgid = int.from_bytes(data[:2], 'big') >> 4

            send(PREAMB + datalen + data + crc)
            flush()

            if msgid == anchor and i % interval == 0:
                # Reimplement this in a more graceful way...
                if not RTCM['1006'] and anchor == 1005:
                    RTCM['1006'] = genRTCM1006(data)

                for msg in msgs:
                    send(RTCM[msg])
                    flush()

except Exception as e:
    from traceback import print_exc
    if locals().get('logfile'):
        with logfile.open('w') as file:
            print_exc(file=file)
    else:
        print_exc()
    exit(1)
