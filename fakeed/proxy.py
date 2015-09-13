#!/usr/bin/env python3
#
# Simple asynchronous HTTP proxy with tunnelling (CONNECT).
#
# GET/POST proxying based on
# http://groups.google.com/group/python-tornado/msg/7bea08e7a049cf26
#
# Copyright (C) 2012 Senko Rasic <senko.rasic@dobarkod.hr>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import logging
import os
import sys
import socket

from datetime import datetime

import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web
import tornado.httpclient
import tornado.httputil

from urllib.parse import urlparse
from Torrent import TorrentDBConnection

import configparser

from UploadCalculator import UploadCalculator
from functools import lru_cache


FAKEED_HOME = os.environ.get('FAKEED_HOME') or os.path.expanduser('~/.fakeed')

FAKEED_SQLITE_FILE = 'db.sqlite'
FAKEED_CONFIG_FILE = 'config.ini'

logging.basicConfig()
logger = logging.getLogger('fakeed')

logger.setLevel(logging.INFO)

__all__ = ['ProxyHandler', 'run_proxy']


def get_proxy(url):
    url_parsed = urlparse(url, scheme='http')
    proxy_key = '%s_proxy' % url_parsed.scheme
    return os.environ.get(proxy_key)


def parse_proxy(proxy):
    proxy_parsed = urlparse(proxy, scheme='http')
    return proxy_parsed.hostname, proxy_parsed.port


def fetch_request(url, callback, **kwargs):
    proxy = get_proxy(url)
    tornado.httpclient.AsyncHTTPClient.configure(
            'tornado.curl_httpclient.CurlAsyncHTTPClient')
    if proxy:
        logger.debug('Forward request via upstream proxy %s', proxy)
        host, port = parse_proxy(proxy)
        kwargs['proxy_host'] = host
        kwargs['proxy_port'] = port

    req = tornado.httpclient.HTTPRequest(url, **kwargs)
    client = tornado.httpclient.AsyncHTTPClient()
    client.fetch(req, callback)


@lru_cache(maxsize=12)
def find_fakeed_file(filename: str):
    dirs = (FAKEED_HOME, '/etc/fakeed', os.getcwd(), os.path.dirname(os.path.abspath(__file__)))
    for d in dirs:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    raise FileNotFoundError('unable to find file ' + filename)


def get_config():
    config = configparser.RawConfigParser()
    config_file = find_fakeed_file(FAKEED_CONFIG_FILE)
    logger.info('opening config file "%s"', config_file)
    config.read(config_file)
    return config


class ProxyHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ['GET', 'POST', 'CONNECT']
    config = get_config()

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self._db = None
        self._upcalc = None

    @property
    def db(self):
        if self._db is None:
            self._db = TorrentDBConnection(find_fakeed_file(FAKEED_SQLITE_FILE))
        return self._db

    @property
    def upcalc(self):
        if self._upcalc is None:
             self._upcalc = UploadCalculator(self.db, self.config)
        return self._upcalc

    def get_byte_argument(self, name, default=tornado.web.RequestHandler._ARG_DEFAULT):
        ret = self.request.arguments.get(name, tornado.web.RequestHandler._ARG_DEFAULT)
        if ret is tornado.web.RequestHandler._ARG_DEFAULT:
            return default
        return ret[-1]
        
    def compute_etag(self):
        return None

    @tornado.web.asynchronous
    def get(self):
        logger.debug('Handle %s request to %s', self.request.method,
                     self.request.uri)

        def handle_response(response):
            if response.error and not isinstance(response.error, tornado.httpclient.HTTPError):
                self.set_status(500)
                self.write('Internal server error:\n' + str(response.error))
            else:
                reason = tornado.httputil.responses.get(response.code, 'unknown')
                self.set_status(response.code, reason=reason)
                for header in ('Date', 'Cache-Control', 'Server', 'Content-Type', 'Location'):
                    v = response.headers.get(header)
                    if v:
                        self.set_header(header, v)
                v = response.headers.get_list('Set-Cookie')
                if v:
                    for i in v:
                        self.add_header('Set-Cookie', i)
                if response.body:
                    self.write(response.body)
            self.finish()

        body = self.request.body
        if not body:
            body = None
        try:
            uri = self.request.uri
            logger.debug(self.request)
            # vodoo magic begin here
            info_hash = self.request.arguments.get('info_hash')
            if info_hash is not None:  # assume this is a torrent tracker's announce
                netloc = urlparse(self.request.uri).netloc
                downloaded = int(self.get_argument('downloaded', 0))
                uploaded = int(self.get_argument('uploaded', 0))
                if downloaded or uploaded:
                    torrent = self.db.getOrCreate(self.get_byte_argument('info_hash'),
                                                  self.get_byte_argument('peer_id'),
                                                  netloc)

                    torrent.uploaded += uploaded
                    torrent.downloaded += downloaded
                    torrent.left = int(self.get_argument('left', 0))

                    torrent.ip = self.get_argument('ipv4', None) or self.get_argument('ip', None) or torrent.ip
                    torrent.event = self.get_argument('event', torrent.event)

                    uploaded_calc = self.upcalc(torrent, downloaded=downloaded, uploaded=uploaded) or 0

                    uploaded_trick = max(uploaded, uploaded_calc)

                    if torrent.fake_uploaded is None:
                        torrent.fake_uploaded = 0
                    torrent.fake_uploaded += uploaded_trick

                    torrent.tracker_date = datetime.now()
                    # update internal database
                    # TODO WORKER
                    if torrent.id is None:
                        self.db.save(torrent)
                    else:
                        self.db.update(torrent)
                    # let's replace uploaded into uri
                    if uploaded_trick != uploaded:
                        logger.info("replaced uploaded bytes %d with %d", uploaded, uploaded_trick)
                        uri = uri.replace('uploaded=%d' % uploaded, 'uploaded=%d' % uploaded_trick)
            # vodoo magic end here
            headers = self.request.headers
            headers["Accept-Encoding"] = "deflate"
            fetch_request(
                uri, handle_response,
                method=self.request.method, body=body,
                headers=headers, follow_redirects=False,
                decompress_response=False,
                allow_nonstandard_methods=True)
        except tornado.httpclient.HTTPError as e:
            if hasattr(e, 'response') and e.response:
                handle_response(e.response)
            else:
                self.set_status(500)
                self.write('Internal server error:\n' + str(e))
                self.finish()

    @tornado.web.asynchronous
    def post(self):
        return self.get()

    @tornado.web.asynchronous
    def connect(self):
        logger.debug('Start CONNECT to %s', self.request.uri)
        host, port = self.request.uri.split(':')
        client = self.request.connection.stream

        def read_from_client(data):
            upstream.write(data)

        def read_from_upstream(data):
            client.write(data)

        def client_close(data=None):
            if upstream.closed():
                return
            if data:
                upstream.write(data)
            upstream.close()

        def upstream_close(data=None):
            if client.closed():
                return
            if data:
                client.write(data)
            client.close()

        def start_tunnel():
            logger.debug('CONNECT tunnel established to %s', self.request.uri)
            client.read_until_close(client_close, read_from_client)
            upstream.read_until_close(upstream_close, read_from_upstream)
            client.write(b'HTTP/1.0 200 Connection established\r\n\r\n')

        def on_proxy_response(data=None):
            if data:
                first_line = data.splitlines()[0]
                http_v, status, text = first_line.split(None, 2)
                if int(status) == 200:
                    logger.debug('Connected to upstream proxy %s', proxy)
                    start_tunnel()
                    return

            self.set_status(500)
            self.finish()

        def start_proxy_tunnel():
            upstream.write('CONNECT %s HTTP/1.1\r\n' % self.request.uri)
            upstream.write('Host: %s\r\n' % self.request.uri)
            upstream.write('Proxy-Connection: Keep-Alive\r\n\r\n')
            upstream.read_until('\r\n\r\n', on_proxy_response)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        upstream = tornado.iostream.IOStream(s)

        proxy = get_proxy(self.request.uri)
        if proxy:
            proxy_host, proxy_port = parse_proxy(proxy)
            upstream.connect((proxy_host, proxy_port), start_proxy_tunnel)
        else:
            upstream.connect((host, int(port)), start_tunnel)


def run_proxy(port, start_ioloop=True):
    """
    Run proxy on the specified port. If start_ioloop is True (default),
    the tornado IOLoop will be started immediately.
    """
    app = tornado.web.Application([
        (r'.*', ProxyHandler),
    ])
    app.listen(port)
    ioloop = tornado.ioloop.IOLoop.instance()
    if start_ioloop:
        ioloop.start()





def setup():
    try:
        find_fakeed_file(FAKEED_SQLITE_FILE)
    except FileNotFoundError:
        from create_sqlite_db import create_db

        if not os.path.exists(FAKEED_HOME):
            os.mkdir(FAKEED_HOME)
        fakeedfile = os.path.join(FAKEED_HOME, FAKEED_SQLITE_FILE)
        create_db(fakeedfile, find_fakeed_file('torrent.sql'))
    try:
        find_fakeed_file(FAKEED_CONFIG_FILE)
    except FileNotFoundError:
        import ressources

        if not os.path.exists(FAKEED_HOME):
            os.mkdir(FAKEED_HOME)
        with open(os.path.join(FAKEED_HOME, FAKEED_CONFIG_FILE), 'w') as f:
            f.write(ressources.default_config)


if __name__ == '__main__':
    setup()
    port = os.environ.get('FAKEED_PORT')
    port = int(port) if port else 8888
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print("Starting HTTP proxy on port %d" % port)
    run_proxy(port)
