import re
import time
from argparse import ArgumentParser
from math import ceil
from pathlib import Path
from subprocess import run

from mvbs import PROJECT, STR2STR, STR2STR_LOG, NTRIPS_PID_FILE

TAIL = Path('/usr/bin/tail')


def tail(file: Path, n: int):
    return run([TAIL, '-n', str(n), str(file)], text=True, capture_output=True).stdout


parser = ArgumentParser(description='Str2str watchdog')

parser.add_argument('-i', '--interval', dest='interval', required=True, type=int,
                    help="interval (in seconds) for analysing str2str logs")

args = parser.parse_args()

str2str_log = max(STR2STR_LOG.parent.glob(STR2STR.stem + '*.log'), key=lambda file: file.stat().st_mtime)
str2str_regex = re.compile(r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
                           r'\[(.{5})\]\s+(\d+) B\s+(\d+) bps(?:\s+\((\d+)\)\s+(.*))*')

while True:
    while True:
        # Check state once in `args.interval` seconds
        time.sleep(args.interval)

        # If pid file does not exist, mvbs was intentionally stopped
        if not NTRIPS_PID_FILE.exists():
            time.sleep(30)
            continue

        # Check if str2str process is alive
        for i in range(1, 4):
            if run(f'test -d /proc/{NTRIPS_PID_FILE.read_text()}', shell=True).returncode == 0:
                print()
                break
            else:
                print(f"str2str process is dead, assuming restart in progress ({i})...")
                time.sleep(3)
        else:
            print(f"{time.strftime(r'%d.%m.%Y %H:%M:%S')}: str2str is down, restarting mvbs\n")
            break

        # Determine current log file
        str2str_log = max(str2str_log.parent.glob(STR2STR.stem + '*.log'), key=lambda file: file.stat().st_mtime)

        # Read statuses from lines that appeared in log file in last 'interval' period of time
        lines = tail(str2str_log, ceil(args.interval / 5)).split('\n')
        statuses = []
        for line in lines:
            line = line.strip()
            match = str2str_regex.match(line) if line else None
            if match is not None:
                statuses.append(match.group(6))

        # If no successful connection is present in status field (the last item in str2str log entry)
        # for specified interval - str2str is failing, reload mvbs
        if all('/' not in status for status in statuses):
            print(f"{time.strftime(r'%d.%m.%Y %H:%M:%S')}: str2str bad status {statuses}, restarting mvbs\n")
            break
        else:
            ...

    # Restart mvbs
    print(f"{time.strftime(r'%d.%m.%Y %H:%M:%S')}: str2str is down, restarting mvbs\n")
    run(['python', PROJECT / 'mvbs.py', 'restart'], text=True)
    # Give mvbs time to restart and connect to caster
    time.sleep(30)
