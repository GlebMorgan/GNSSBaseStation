import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from subprocess import run

import toml


class StreamStatus(Enum):
    # Original statuses: E: error, -: close, W: wait, C: connect, C: active
    Error = 'E'
    Closed = '-'
    Waiting = 'W'
    Connected = 'C'


def test():
    timestamp_format = r'%Y/%m/%d %H:%M:%S'
    str2str_regex = re.compile(r'(\d{4}\/\d{2}\/\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
                               r'\[(.{5})\]\s+(\d+ B)\s+(\d+ bps)'
                               r'(?:\s+\((\d+)\)\s+(.*))*')

    res = str2str_regex.match('2020/02/26 06:02:05 [C----]          0 B       0 bps (1) OK')

    stats = res.groups()
    print(stats)

    print(datetime.strptime(stats[0], timestamp_format).year)
    print(StreamStatus(stats[1][1]))
    print(stats[5])


def get_str2str_status():
    logfile = Path('/home/pi/app/logs/str2str.log')
    fields = 'timestamp', 'state', 'received', 'rate', 'streams', 'info'
    str2str_regex = re.compile(r'(\d{4}\/\d{2}\/\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
                               r'\[(.{5})\]\s+(\d+ B)\s+(\d+ bps)'
                               r'(?:\s+\((\d+)\)\s+(.*))*')
    if not logfile.exists():
        return None

    lines = logfile.read_text().split('\n')
    status_line = lines[-2] if not lines[-1] else lines[-1]

    if status_line.strip() == 'stream server stop':
        return None

    match = str2str_regex.match(status_line)
    if match is None:
        return None

    return {field: value for field, value in zip(fields, match.groups())}


def get_ntrips_status():
    mvbs_regex = re.compile(r'NTRIP server is (\S*)')
    args = ['python', '/home/pi/app/mvbs.py', 'state']
    result = run(args, text=True, capture_output=True).stdout
    return mvbs_regex.search(result).groups()[0]


def get_status():
    configfile = '/home/pi/app/config.toml'
    str2str_timestamp_fmt = r'%Y/%m/%d %H:%M:%S'
    target_timestamp_fmt = r'%d.%m.%Y %H:%M:%S'

    config = toml.load(str(configfile))
    ntripc_config = config['NTRIPC']

    ntrips_status = get_ntrips_status()
    if ntrips_status == 'running':
        stream_status = get_str2str_status()
        timestamp = datetime.strptime(stream_status['timestamp'], str2str_timestamp_fmt)
    else:
        stream_status = None
        timestamp = datetime.now()

    data = {
        'Updated':              datetime.strftime(timestamp, target_timestamp_fmt),
        'Device name':          config['name'],
        'NTRIP server status':  ntrips_status.capitalize(),
        'NTRIP caster':         ntripc_config['domain'],
        'Target port':          ntripc_config['port'],
        'Mountpoint':           ntripc_config['mountpoint'],
        'Username':             ntripc_config['username'],
        'Base station mode':    config['BASE']['mode'],
    }

    if stream_status is not None:
        data.update({
            'Input RTCM3 stream':   StreamStatus(stream_status['state'][0]).name,
            'Output RTCM3 stream':  StreamStatus(stream_status['state'][1]).name,
            'Bytes received':       stream_status['received'],
            'Transmission rate':    stream_status['rate'],
            'Number of streams':    stream_status['streams'],
            'Connection status':    stream_status['info'].strip(),
        })

    return data


if __name__ == '__main__':
    print(*(f'{name.ljust(20)} {value}' for name, value in get_status().items()), sep='\n')
