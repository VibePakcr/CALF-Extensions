"""Test-only worker command. Production CLI cannot select this transport."""
import http.client
import json
import os
import ssl
import sys
import time
from calf_extensions.repository.http_reader import strict_json
from calf_extensions.repository.http_worker import perform

payload=strict_json(sys.stdin.buffer.read(65537));mode=sys.argv[2] if len(sys.argv)>2 else 'http'
if payload.get('token') and any(payload['token'] in value for value in os.environ.values()):
    print(json.dumps({'error':'REQUEST_REFUSED'}));raise SystemExit(0)
if mode=='hang':
    while True:time.sleep(10)
if mode=='overflow':
    sys.stdout.write('x'*(payload['limit']*2+100000));sys.stdout.flush();raise SystemExit(0)
port=int(sys.argv[1]);factory=(lambda host,timeout:http.client.HTTPSConnection('127.0.0.1',port,timeout=timeout,context=ssl.create_default_context())) if mode=='tls' else (lambda host,timeout:http.client.HTTPConnection('127.0.0.1',port,timeout=timeout))
sys.stdout.write(json.dumps(perform(payload,factory),ensure_ascii=True));sys.stdout.flush()
