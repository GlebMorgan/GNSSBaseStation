from itertools import count
from time import sleep

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from Configurator.controller import configView
import json

def random_status_generator(rate):
    from random import random, choice
    from time import strftime
    tempers = ('primary', 'secondary', 'success', 'info', 'warning', 'dark')

    for n in count():
        statusView = [
            {'name': 'power-status', 'value': f'Power status {n}', 'temper': choice(tempers)},
            {'name': 'base-status', 'value': f'Base status {n}', 'temper': choice(tempers)},
            {'name': 'ntripc-status', 'value': f'NTRIPC status {n}', 'temper': choice(tempers)},
            {'name': 'ntrips-status', 'value': f'NTRIPS status {n}', 'temper': choice(tempers)},
            {'name': 'usb-voltage-bar', 'value': f'{4.75+random()/2:.2f}V'},
            {'name': 'lemo-voltage-bar', 'value': f'{12.1+random():.2f}V'},
            {'name': 'ups-voltage-bar', 'value': f'{3.7+random()/3:.2f}V'},
            {'name': 'base-details', 'value': 'Some base details'},
            {'name': 'rtcm-stream-status', 'value': 'RTCM status'},
            {'name': 'rtcm-stream-speed', 'value': f'{round(random()*100, 1)} KBit/s'},
            {'name': 'rtcm-stream-details', 'value': 'RTCM stream details'},
            {'name': 'timestamp', 'value': strftime('%d.%m.%Y %H:%M:%S')},
        ]

        yield f'data: {json.dumps(statusView)}\n\n'
        sleep(rate)

def config_ui(request):
    context = {'pageTitle': "ZED F9P Config", **configView}
    return render(request, 'ui.html', context)

def status_updates(request):
    return StreamingHttpResponse(random_status_generator(rate=0.5), content_type='text/event-stream')
