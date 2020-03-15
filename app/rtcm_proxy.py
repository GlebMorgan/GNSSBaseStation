#!/usr/bin/env python3

from pathlib import Path
from argparse import ArgumentParser, ArgumentError
from serial import Serial
import sys


PREAMB = b'\xD3'
RTCM = {
    1008: b'\xD3\x00\x06\x3F\x00\x00\x00\x00\x00\x99\x25\xCA'
}


parser = ArgumentParser(description='RTCM3 stream proxy')

parser.add_argument('-in', '--input-stream',
                    dest='input', metavar='INPUT_STREAM',
                    help="Input RTCM stream (default: <stdin>). "
                         "Supported stream formats: "
                         "serial://port:baudrate:bytesize:parity:stopbits, "
                         "file://filepath")

parser.add_argument('-out', '--output-stream',
                    dest='output', metavar='OUTPUT_STREAM',
                    help="Output RTCM stream (default: <stdout>)."
                         "Supported stream format: file://filepath")

parser.add_argument('-a', '--anchor', required=True, dest='anchor', type=int,
                    help="RTCM message ID that would be searched in input stream "
                         "and serve as a trigger for injecting specified RTCM messages")

parser.add_argument('-m', '--messages', nargs='+', default=[], dest='msgs', metavar='MSG',
                    help="RTCM message IDs to inject after 'anchor' message")

parser.add_argument('-l', '--log-file', dest='log',
                    help="File path for error output")


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
    try:
        msgs = tuple(RTCM[int(msgid)] for msgid in args.msgs)
    except (TypeError, ValueError) as e:
        parser.error(f"{argument}: encountered invalid RTCM message id: {e}")
    except KeyError as e:
        parser.error(f"{argument}: encountered unsupported RTCM message id: {e}")

    argument = 'argument -l/--log-file'
    logfile = Path(args.log).resolve()
    if not logfile.parent.is_dir():
        parser.error(f"{argument}: invalid path: '{args.log}'")

    send = output.write
    flush = output.flush
    #
    # print('input: ', args.input)
    # print('output: ', args.output)
    # print('anchor: ', args.anchor)
    # print('msgs', args.msgs)
    # print('log: ', args.log)
    # input()
    # exit(0)

    with source, output:
        while True:
            while source.read(len(PREAMB)) != PREAMB: pass
            datalen = source.read(2)
            data = source.read(int.from_bytes(datalen, 'big', signed=False))
            crc24 = source.read(3)

            msgid = int.from_bytes(data[:2], 'big', signed=False) >> 4

            send(PREAMB + datalen + data + crc24)
            flush()

            if msgid == args.anchor:
                for msg in msgs:
                    send(msg)
                    flush()

except Exception as e:
    if locals().get('logfile'):
        logfile.write_text(str(e))
    exit(1)
