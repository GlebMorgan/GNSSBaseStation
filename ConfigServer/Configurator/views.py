import json
import re

from django.http import StreamingHttpResponse, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse

from Configurator.controller import configView, RegexDict, Action, status_updater


def config_ui(request):
    context = {'pageTitle': "ZED F9P Config", **configView}
    return render(request, 'ui.html', context)


def status_updates(request):
    return StreamingHttpResponse(status_updater(), content_type='text/event-stream')


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
