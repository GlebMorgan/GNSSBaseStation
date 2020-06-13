# TODO: These values should be updated by JS!

configView = {
    'power': {
        'active': True,
        'voltages': {
            'usb': {'min': 4, 'max': 6},
            'lemo': {'min': 8, 'max': 20},
            'ups': {'min': 3, 'max': 4.5},
        },
        'thresholds': {
            'shutdown': 3.7,
            'recovery': 4.2,
        },
        'timeout': 3,
    },

    'base': {
        'active': True,
        'mode': 'fixed',
        'observe': 180,
        'accuracy': 5,
        'coords': {
            'lat': 27.5590547,
            'lon': 53.9006643,
            'hgt': 289,
        },
    },

    'ntripc': {
        'active': True,
        'domain': 'https://rtk2go.com',
        'port': '2021',
        'mountpoint': 'test',
        'pass': 'password',
        'str': 'Testing;RTCM 3.1;1008(1);1;GPS;SNIP;BY;27.00;54.00;0;0;sNTRIP;;None;B;N;0;',
    },

    'ntrips': {
        'active': False,
        'msgs': [
            {'id': 1005, 'enabled': True, 'description': '1005 message description', 'speed': 1},
            {'id': 1033, 'disabled': True, 'description': '1033 message description', 'speed': 5},
        ],
    },
}
