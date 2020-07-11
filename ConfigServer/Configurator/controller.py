import json
import re
from datetime import datetime
from itertools import count
from pathlib import Path
from subprocess import run
from time import sleep

import toml

from StatusServer.controller import StreamStatus
from StatusServer.controller import get_str2str_status, get_ntrips_status, format_unit


PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT / 'config.toml'
MVBS_PATH = PROJECT / 'mvbs.py'
MVBS_PID_FILE = Path('/run/user/bs/ntrips.pid')

CONFIG = toml.load(str(CONFIG_FILE))
UPDATE_PERIOD = 1


def getConfigView():
    base_status = get_ntrips_status()
    return {
        'power': {
            'active': True,
            'voltages': {
                'usb': {'min': 4, 'max': 6},
                'lemo': {'min': 8, 'max': 20},
                'ups': {'min': 3, 'max': 4.5},
            },
            'thresholds': {
                'shutdown': CONFIG['POWER']['shutdown'],
                'recovery': CONFIG['POWER']['recovery'],
            },
            'timeout': CONFIG['POWER']['timeout'],
        },

        'base': {
            'active': base_status == 'running',
            'mode': CONFIG['BASE']['mode'].lower(),
            'observe': CONFIG['BASE']['observe'],
            'accuracy': CONFIG['BASE']['accuracy'],
            'coords': {
                'lat': CONFIG['BASE']['lat'],
                'lon': CONFIG['BASE']['lon'],
                'hgt': CONFIG['BASE']['hgt'],
            },
        },

        'ntripc': {
            'active': base_status == 'running',
            'domain': CONFIG['NTRIPC']['domain'],
            'port': CONFIG['NTRIPC']['port'],
            'mountpoint': CONFIG['NTRIPC']['mountpoint'],
            'pass': CONFIG['NTRIPC']['password'],
            'str': CONFIG['NTRIPC']['str'],
        },

        'ntrips': {
            'active': base_status == 'running',
            'msgs': [
                {
                    'id': 1006,
                    'enabled': 1006 in CONFIG['NTRIPS']['inject'],
                    'description': 'Stationary RTK Reference Station ARP with Antenna Height',
                    'speed': 1,
                },
                {
                    'id': 1008,
                    'enabled': 1008 in CONFIG['NTRIPS']['inject'],
                    'description': 'Antenna Descriptor and Serial Number',
                    'speed': 1,
                },
                {
                    'id': 1033,
                    'enabled': 1033 in CONFIG['NTRIPS']['inject'],
                    'description': 'Receiver and Antenna Descriptors',
                    'speed': 5,
                },
            ],
        },
    }


def random_status_generator(rate):
    from random import random, choice
    from time import strftime
    tempers = ('primary', 'secondary', 'success', 'info', 'warning', 'danger', 'dark')

    for n in count():
        statusView = [
            {'name': 'power-status', 'value': f'Power status {n}', 'temper': choice(tempers)},
            {'name': 'base-status', 'value': f'Base status {n}', 'temper': choice(tempers)},
            {'name': 'ntripc-status', 'value': f'NTRIPC status {n}', 'temper': choice(tempers)},
            {'name': 'ntrips-status', 'value': f'NTRIPS status {n}', 'temper': choice(tempers)},
            {'name': 'usb-voltage-bar', 'value': f'{4.75 + random() / 2:.2f}V'},
            {'name': 'lemo-voltage-bar', 'value': f'{12.1 + random():.2f}V'},
            {'name': 'ups-voltage-bar', 'value': f'{3.7 + random() / 3:.2f}V'},
            {'name': 'base-details', 'value': 'Some base details'},
            {'name': 'rtcm-stream-status', 'value': 'RTCM status'},
            {'name': 'rtcm-stream-speed', 'value': f'{round(random() * 100, 1)} KBit/s'},
            {'name': 'rtcm-stream-details', 'value': 'RTCM stream details'},
            {'name': 'timestamp', 'value': strftime('%d.%m.%Y %H:%M:%S')},
        ]

        yield f'data: {json.dumps(statusView)}\n\n'
        sleep(rate)


def status_updater():
    for n in count():
        yield f'data: {json.dumps(get_status_updates())}\n\n'
        sleep(UPDATE_PERIOD)


def get_rtk2go_status(caster_config):
    if 'rtk2go' not in caster_config['domain'].lower():
        return 'Unknown'

    url = 'http://rtk2go.com:{config[port]}/SNIP::MOUNTPT?NAME={config[mountpoint]}'.format(config=caster_config)
    result = run(['curl', '-s', url], text=True, capture_output=True)

    if result.returncode != 0:
        # NOTE: Sometimes RTK2Go replies with no data => curl fails with returncode 52
        return 'Unreachable'
    elif 'Base Station Mount Point Details:' not in result.stdout:
        return 'Down'
    else:
        return 'Up'


def get_zero2go_status():
    """
    Get List[int, int, int] of zero2go input channels [chA, chB, chC]
    """

    voltages = [None, None, None]
    for channel in range(3):
        args = ['i2cget', '-y', '0x01', '0x29']
        integerPart = run(args + [str(channel*2 + 1)], text=True, capture_output=True)
        decimalPart = run(args + [str(channel*2 + 2)], text=True, capture_output=True)
        if all(result.returncode == 0 and result.stdout for result in (integerPart, decimalPart)):
            voltages[channel] = int(integerPart.stdout, 0) + int(decimalPart.stdout, 0) / 100
        else:
            voltages[channel] = 0
    return voltages


def get_status_updates():
    # TODO: Refactor to get_status_updates()
    str2str_timestamp_fmt = r'%Y/%m/%d %H:%M:%S'
    target_timestamp_fmt = r'%d.%m.%Y %H:%M:%S'

    voltages = get_zero2go_status()
    active_channel = ('usb', 'lemo', 'ups')[voltages.index(max(voltages))]

    base_status = get_ntrips_status()
    str2str_details = None
    if base_status == 'running':
        base_temper = 'success'
        str2str_details = get_str2str_status()
        if str2str_details:
            server_status = 'Up'
            server_temper = 'success'
            timestamp = datetime.strptime(str2str_details['timestamp'], str2str_timestamp_fmt)
        else:
            server_status = 'Error'
            server_temper = 'warning'
            timestamp = datetime.now()
    else:
        base_temper = {
            'killed': 'danger',
            'stopped': 'dark',
        }.get(base_status, 'warning')

        server_status = 'Down'
        server_temper = 'dark'
        timestamp = datetime.now()

    if not str2str_details:
        str2str_details = {
            'state': 'Down',
            'received': 0,
            'rate': 0,
            'streams': 0,
            'info': '',
        }

    caster_status = get_rtk2go_status(CONFIG['NTRIPC'])
    caster_temper = {
        'Unknown': 'danger',
        'Unreachable': 'secondary',
        'Down': 'dark',
        'Up': 'success',
    }.get(caster_status, 'warning')

    base_mode_description = {
        'disabled': 'Rover mode',
        'svin': 'Coordinates are determined dynamically',
        'fixed': 'Coordinates specified below are used'
    }

    stream_status_tempers = {
        'Down': 'dark',
        'Error': 'danger',
        'Closed': 'secondary',
        'Waiting': 'warning',
        'Connected': 'success',
    }

    if str2str_details['state'] == 'Down':
        rtcm_status = dict.fromkeys(('input', 'output'), 'Down')
    else:
        rtcm_status = {
            'input': StreamStatus(str2str_details['state'][0]).name,
            'output': StreamStatus(str2str_details['state'][1]).name,
        }

    return [
        {'name': 'power-status', 'value': active_channel.upper(), 'temper': 'success'},
        {'name': 'base-status', 'value': base_status.upper(), 'temper': base_temper},
        {'name': 'ntripc-status', 'value': caster_status.upper(), 'temper': caster_temper},
        {'name': 'ntrips-status', 'value': server_status.upper(), 'temper': server_temper},
        {'name': 'usb-voltage-bar', 'value': f'{voltages[0]}V'},
        {'name': 'lemo-voltage-bar', 'value': f'{voltages[1]}V'},
        {'name': 'ups-voltage-bar', 'value': f'{voltages[2]}V'},  # may be useful: format = :.2f
        {'name': 'base-details', 'value': base_mode_description[CONFIG['BASE']['mode'].lower()]},
        {'name': 'rtcm-input-stream-status', 'value': rtcm_status['input'],
         'temper': stream_status_tempers[rtcm_status['input']]},
        {'name': 'rtcm-input-stream-details', 'value': format_unit(int(str2str_details['received']), 'B', decimals=2)},
        {'name': 'rtcm-output-stream-status', 'value': rtcm_status['output'],
         'temper': stream_status_tempers[rtcm_status['output']]},
        {'name': 'rtcm-output-stream-details',
         'value': format_unit(int(str2str_details['rate']), 'B/s', decimals=2)},
        {'name': 'rtcm-stream-details', 'value': str2str_details['info']},
        {'name': 'timestamp', 'value': datetime.strftime(timestamp, target_timestamp_fmt)},
    ]


def mvbs_handler(command, flags=()):
    result = run([str(MVBS_PATH), command, *flags])
    return not bool(result.returncode)


class RegexDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__patterns__ = {}
        for key in tuple(self.keys()):
            if isinstance(key, re.Pattern):
                self.__patterns__[key] = self[key]
                super().__delitem__(key)

    def __getitem__(self, item):
        try:
            return super().__getitem__(item)
        except KeyError:
            if not isinstance(item, str):
                raise
            for regex, value in self.__patterns__.items():
                if re.fullmatch(regex, item):
                    return value
            raise

    def __setitem__(self, key, value):
        if isinstance(key, re.Pattern):
            self.__patterns__[key] = value
        else:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self.__patterns__:
            del self.__patterns__[key]
        else:
            super().__delitem__(key)

    def get(self, item, default=None):
        try:
            return self.__getitem__(item)
        except KeyError:
            return default


class Action:
    mvbs_action = None
    config_changed = False
    inject = []
    flags = []

    @classmethod
    def alterConfig(cls, item, value):
        module, *_, parameter = item.split('-')
        currentValue = CONFIG[module.upper()][parameter]

        try:
            value = type(currentValue)(value)
        except TypeError:
            raise TypeError(f"Failed to change configuration: "
                            f"invalid parameter type {type(value)}, expected {type(currentValue)}")

        if value != currentValue:
            cls.config_changed = True
            CONFIG[module.upper()][parameter] = value

            if parameter.startswith('base-'):
                cls.flags.append('-c')
            if parameter.startswith('power-'):
                cls.flags.append('-z')

    @classmethod
    def switchBaseStation(cls, item, value):
        if value == 'on' and not MVBS_PID_FILE.exists():
            cls.mvbs_action = 'start'
        elif value == 'off' and MVBS_PID_FILE.exists():
            cls.mvbs_action = 'stop'

    @classmethod
    def switchCaster(cls, item, value):
        return NotImplemented

    @classmethod
    def switchServer(cls, item, value):
        return NotImplemented

    @classmethod
    def switchRTCM(cls, item, value):
        msgs = CONFIG['NTRIPS']['inject']
        target_msg = int(item.strip('rtcm-'))
        value = (value == 'on')
        if target_msg in msgs and value is False:
            msgs.remove(target_msg)
        elif target_msg not in msgs and value is True:
            msgs.append(target_msg)

    @classmethod
    def injectRTCM(cls, item, value):
        msg_num = re.search(r'rtcm-(\d*)', item).groups()[0]
        if value == 'on':
            cls.inject.append(int(msg_num))

    @classmethod
    def reset_uBlox(cls):
        results = [
            mvbs_handler('stop'),
            mvbs_handler('reset'),
            mvbs_handler('start'),
        ]
        if all(returncode == 0 for returncode in results):
            return 0
        elif results[1] != 0:
            return results[1]
        else:
            return max(results)

    @classmethod
    def dispatch(cls, params: dict, mapping: dict):
        # params: Dict[<ui element names>, <one-element lists (values)>] - expected POST request here
        # mapping: Dict[<ui element names>, <handler method names>] - maps frontend controls to config actions
        for key, value in params.items():
            handler = mapping.get(key, None)
            if handler not in (None, NotImplemented):
                handler(key, value[0])

        if set(cls.inject) != set(CONFIG['NTRIPS']['inject']):
            CONFIG['NTRIPS']['inject'] = cls.inject
            cls.config_changed = True

        if MVBS_PID_FILE.exists() and cls.config_changed:
            cls.mvbs_action = 'restart'

        print(f"Config changed: {cls.config_changed}")
        print(f"Action: {cls.mvbs_action}")

        if cls.config_changed:
            with CONFIG_FILE.open('tw', encoding='utf-8') as file:
                toml.dump(CONFIG, file)
                # TODO: preserve comments

        if cls.mvbs_action:
            mvbs_handler(cls.mvbs_action, flags=cls.flags)

        cls.mvbs_action = None
        cls.config_changed = False
        cls.inject = []
        cls.flags = []
