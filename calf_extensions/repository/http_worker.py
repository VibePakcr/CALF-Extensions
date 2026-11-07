"""Single owned HTTPS request. Input credentials stay in pipes; diagnostics are fixed codes."""
import base64
import http.client
import json
import ssl
import sys
from urllib.parse import urlsplit
from .http_reader import API_VERSION,HTTPError,RequestSpec,SAFE_HEADERS,follow_url,strict_json
from .registrations import Registration


def perform(payload,connection_factory=None):
    try:
        if not isinstance(payload,dict) or set(payload)!={'registration','spec','url','token','etag','limit','timeout'}:raise HTTPError('REQUEST_REFUSED')
        registration=Registration(**payload['registration']);spec=RequestSpec(**payload['spec']);url=payload['url'];base=spec.url(registration)
        if url!=base:
            try:follow_url(registration,spec,base,url,pagination=True)
            except HTTPError:follow_url(registration,spec,base,url)
        if payload['limit']!=spec.response_limit(registration) or payload['timeout']!=5:raise HTTPError('REQUEST_REFUSED')
        token=payload['token'];etag=payload['etag']
        if token is not None and (not isinstance(token,str) or len(token)>8192 or not token.isascii() or any(ord(c)<33 or ord(c)==127 for c in token)):raise HTTPError('REQUEST_REFUSED')
        if etag is not None and (not isinstance(etag,str) or len(etag)>8192 or '\r' in etag or '\n' in etag):raise HTTPError('REQUEST_REFUSED')
        u=urlsplit(url);headers={'Accept':'application/vnd.github+json' if registration.provider=='github' else 'application/json','Accept-Encoding':'identity','User-Agent':'CALF-Repository/0.1-preview'}
        if registration.provider=='github':headers['X-GitHub-Api-Version']=API_VERSION
        if token:headers['Authorization' if registration.provider=='github' else 'PRIVATE-TOKEN']=('Bearer '+token) if registration.provider=='github' else token
        if etag:headers['If-None-Match']=etag
        connection=connection_factory(u.hostname,payload['timeout']) if connection_factory else http.client.HTTPSConnection(u.hostname,timeout=payload['timeout'],context=ssl.create_default_context())
        try:
            connection.request(spec.method,u.path+('?' + u.query if u.query else ''),headers=headers)
            response=connection.getresponse();output={}
            for key,value in response.getheaders():
                key=key.lower()
                if key in SAFE_HEADERS:
                    if key in output or len(value)>8192:raise HTTPError('HTTP_IO')
                    output[key]=value
            if response.getheader('Content-Encoding','identity').lower() not in {'identity',''}:raise HTTPError('HTTP_IO')
            lengths=[v for k,v in response.getheaders() if k.lower()=='content-length']
            if len(lengths)>1 or lengths and not lengths[0].isdigit():raise HTTPError('HTTP_IO')
            has_body=spec.method!='HEAD' and response.status not in {204,304}
            if has_body and lengths and int(lengths[0])>payload['limit']:raise HTTPError('HTTP_RESPONSE_LIMIT')
            data=response.read(payload['limit']+1)
            if has_body and lengths and len(data)!=int(lengths[0]):raise HTTPError('HTTP_IO')
            if len(data)>payload['limit']:raise HTTPError('HTTP_RESPONSE_LIMIT')
            return {'status':response.status,'headers':output,'body':base64.b64encode(data).decode('ascii')}
        finally:connection.close()
    except HTTPError as e:return {'error':e.code if e.code in {'HTTP_RESPONSE_LIMIT','REQUEST_REFUSED'} else 'HTTP_IO'}
    except Exception:return {'error':'HTTP_IO'}


def main():
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:return {'error':'REQUEST_REFUSED'}
        return perform(strict_json(raw))
    except Exception:return {'error':'REQUEST_REFUSED'}

if __name__=='__main__':
    sys.stdout.write(json.dumps(main(),ensure_ascii=True,allow_nan=False));sys.stdout.flush()
