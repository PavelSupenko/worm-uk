#!/usr/bin/env python3
"""Cloudflare R2 access for the voiceover files (S3 API, stdlib only).

Credentials come from the environment (set them in ~/.zshrc, never commit them):
R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_URL.

Usage:
    python3 tools/r2.py check    # credentials, public URL and CORS, without writing anything
    python3 tools/r2.py list     # files in the bucket
"""
import datetime
import hashlib
import hmac
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

VARIABLES = ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET', 'R2_PUBLIC_URL')
REGION = 'auto'
SERVICE = 's3'
S3_NS = '{http://s3.amazonaws.com/doc/2006-03-01/}'
USER_AGENT = 'worm-uk-tools'
SITE_ORIGIN = 'https://pavelsupenko.github.io'


def config():
    missing = [name for name in VARIABLES if not os.environ.get(name)]
    if missing:
        raise SystemExit(f'Missing environment variables: {", ".join(missing)}')
    return {name: os.environ[name].strip().rstrip('/') for name in VARIABLES}


def _hmac(key, text):
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def _quote(text, safe='-_.~'):
    return urllib.parse.quote(str(text), safe=safe)


def _send(url, method, headers=None, body=None):
    """Returns (status, headers, body); HTTP errors are returned, not raised."""
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={'User-Agent': USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def s3_request(cfg, method, key='', query=None, body=b'', headers=None):
    """A request to the bucket signed with AWS Signature Version 4."""
    host = f'{cfg["R2_ACCOUNT_ID"]}.r2.cloudflarestorage.com'
    path = f'/{cfg["R2_BUCKET"]}' + (f'/{_quote(key, safe="/-_.~")}' if key else '')
    canonical_query = '&'.join(f'{_quote(k)}={_quote(v)}' for k, v in sorted((query or {}).items()))
    amz_date = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    date = amz_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    signed_headers = {'host': host, 'x-amz-content-sha256': payload_hash, 'x-amz-date': amz_date}
    signed_headers.update({k.lower(): v for k, v in (headers or {}).items()})
    names = ';'.join(sorted(signed_headers))
    canonical_headers = ''.join(f'{k}:{str(signed_headers[k]).strip()}\n' for k in sorted(signed_headers))
    canonical_request = '\n'.join([method, path, canonical_query, canonical_headers, names, payload_hash])
    scope = f'{date}/{REGION}/{SERVICE}/aws4_request'
    string_to_sign = '\n'.join(['AWS4-HMAC-SHA256', amz_date, scope,
                                hashlib.sha256(canonical_request.encode()).hexdigest()])
    key_bytes = _hmac(f'AWS4{cfg["R2_SECRET_ACCESS_KEY"]}'.encode(), date)
    for part in (REGION, SERVICE, 'aws4_request'):
        key_bytes = _hmac(key_bytes, part)
    signature = hmac.new(key_bytes, string_to_sign.encode(), hashlib.sha256).hexdigest()
    signed_headers['authorization'] = (f'AWS4-HMAC-SHA256 Credential={cfg["R2_ACCESS_KEY_ID"]}/{scope}, '
                                       f'SignedHeaders={names}, Signature={signature}')
    del signed_headers['host']  # urllib sets it from the URL
    url = f'https://{host}{path}' + (f'?{canonical_query}' if canonical_query else '')
    return _send(url, method, signed_headers, body if method in ('PUT', 'POST') else None)


def list_files(cfg, prefix=''):
    """[(key, size)] of every file under the prefix."""
    files, token = [], None
    while True:
        query = {'list-type': '2', 'prefix': prefix}
        if token:
            query['continuation-token'] = token
        status, _, body = s3_request(cfg, 'GET', query=query)
        if status != 200:
            raise SystemExit(f'Listing the bucket failed: HTTP {status}\n{body.decode(errors="replace")[:500]}')
        root = ET.fromstring(body)
        for item in root.iter(f'{S3_NS}Contents'):
            files.append((item.findtext(f'{S3_NS}Key'), int(item.findtext(f'{S3_NS}Size'))))
        token = root.findtext(f'{S3_NS}NextContinuationToken')
        if not token:
            return files


def public_url(cfg, key):
    return f'{cfg["R2_PUBLIC_URL"]}/{urllib.parse.quote(key)}'


def put_file(cfg, key, data, content_type, cache_control='public, max-age=31536000, immutable'):
    """Uploads bytes and checks that the public URL serves them."""
    status, _, body = s3_request(cfg, 'PUT', key, body=data,
                                 headers={'content-type': content_type, 'cache-control': cache_control})
    if status != 200:
        raise SystemExit(f'Upload of {key} failed: HTTP {status}\n{body.decode(errors="replace")[:500]}')
    url = public_url(cfg, key)
    status, headers, _ = _send(url, 'HEAD')
    if status != 200 or int(headers.get('Content-Length', -1)) != len(data):
        raise SystemExit(f'{url} is not served correctly after the upload (HTTP {status})')
    return url


def delete_file(cfg, key):
    status, _, body = s3_request(cfg, 'DELETE', key)
    if status not in (200, 204):
        raise SystemExit(f'Deleting {key} failed: HTTP {status}\n{body.decode(errors="replace")[:500]}')


def check(cfg):
    files = list_files(cfg)
    print(f'credentials: OK, bucket "{cfg["R2_BUCKET"]}" has {len(files)} files')

    # A file that doesn't exist: 404 means the public URL serves the bucket
    probe = f'{cfg["R2_PUBLIC_URL"]}/check-{uuid.uuid4().hex}.txt'
    status, _, _ = _send(probe, 'GET')
    public = {404: 'OK (serves the bucket)', 401: 'access denied: is the public URL enabled?',
              403: 'access denied: is the public URL enabled?'}.get(status, f'unexpected HTTP {status}')
    print(f'public URL: {public}')

    status, headers, _ = _send(probe, 'OPTIONS', {
        'Origin': SITE_ORIGIN, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'range'})
    allowed = headers.get('Access-Control-Allow-Origin') if headers else None
    print(f'CORS for {SITE_ORIGIN}: {"OK" if allowed in (SITE_ORIGIN, "*") else f"not allowed (HTTP {status})"}')


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    cfg = config()
    if command == 'check':
        check(cfg)
    elif command == 'list':
        for key, size in list_files(cfg):
            print(f'{size / 1048576:8.1f} MB  {cfg["R2_PUBLIC_URL"]}/{key}')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
