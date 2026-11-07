"""Frozen delivery requirements for byte-preserving external-video intake."""
import re


def delivery_profile(value):
    # The original encoder preview keeps its original 720p contract unchanged.
    # This intake never encodes: bounded HD/UHD delivery requirements are explicit.
    fields={'width','height','fps','startMs','durationMs','audio','maxBlackMs','maxSilenceMs'}
    if not isinstance(value,dict) or set(value)!=fields:raise ValueError('delivery_profile_fields')
    for key,maximum in [('width',3840),('height',2160)]:
        if type(value[key]) is not int or not 16<=value[key]<=maximum or value[key]%2:
            raise ValueError('delivery_'+key+'_range')
    if type(value['fps']) is not int or value['fps'] not in (24,25,30):raise ValueError('delivery_fps')
    if type(value['startMs']) is not int or value['startMs']!=0:raise ValueError('intake_cannot_trim')
    duration=value['durationMs']
    if type(duration) is not int or not 100<=duration<=30000 or duration*value['fps']%1000:
        raise ValueError('delivery_duration')
    if type(value['audio']) is not bool:raise ValueError('delivery_audio')
    for key in ['maxBlackMs','maxSilenceMs']:
        if value[key] is not None and (type(value[key]) is not int or not 100<=value[key]<=duration):
            raise ValueError('delivery_'+key)
    if not value['audio'] and value['maxSilenceMs'] is not None:raise ValueError('silence_check_requires_audio')
    return dict(value)


def text(value,limit,code):
    if not isinstance(value,str) or not value.strip() or len(value.encode('utf-8'))>limit or '\x00' in value:
        raise ValueError(code)
    return value


def hex_digest(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ValueError('handoff_digest')
    return value
