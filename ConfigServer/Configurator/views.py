import json
import re
from itertools import count
from subprocess import run
from time import sleep

from django.http import StreamingHttpResponse, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse

from Configurator.controller import configView, RegexDict, Action


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

def submit_config(request):

    actionMapping = RegexDict({
        'power': NotImplemented,
        'power-shutdown-voltage': NotImplemented,
        'power-recovery-voltage': NotImplemented,
        'power-poweroff-timeout': NotImplemented,
        'base': Action.switchBaseStation,
        'base-mode': Action.alterConfig,
        'base-observe': Action.alterConfig,
        'base-accuracy': Action.alterConfig,
        'base-coord-system': NotImplemented,
        'base-coord-lat': Action.alterConfig,
        'base-coord-lon': Action.alterConfig,
        'base-coord-hgt': Action.alterConfig,
        'ntripc': Action.switchCaster,
        'ntripc-url': Action.alterConfig,
        'ntripc-port': Action.alterConfig,
        'ntripc-mountpoint': Action.alterConfig,
        'ntripc-password': Action.alterConfig,
        'ntripc-str': Action.alterConfig,
        'ntrips': Action.switchServer,
        re.compile(r'rtcm-(\d{4})'): Action.switchServer,
        re.compile(r'rtcm-(\d{4})-rate'): NotImplemented,
    })
    newConfig = dict.fromkeys(('power', 'base', 'ntrips', 'ntripc'), ['off'])
    newConfig.update(request.POST)

    # TEMP: temporary disable reconfiguration not to break mvbs operation
    # Action.dispatch(newConfig, actionMapping)

    # return HttpResponseRedirect(reverse('static-status'))
    return HttpResponseRedirect(reverse('config'))


def reset_uBlox(request):
    response = {}
    query = request.POST['query']
    if query == 'uBlox reset':
        resetResult = Action.reset_uBlox()
        if resetResult is False:
            response['status'] = 'ERROR'
            response['msg'] = 'uBlox reset error'
        else:
            response['status'] = 'OK'
            response['msg'] = 'uBlox reset successful'
    else:
        response['status'] = 'BAD_QUERY'
        response['msg'] = f"Unknown query {query}"
    return HttpResponse(json.dumps(response), content_type='text/event-stream')
