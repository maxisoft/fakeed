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

from datetime import datetime, timedelta

import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web
import tornado.httpclient


from urllib.parse import urlparse

from SqlTool import Row, Connection

FAKEED_DIR = os.path.expanduser('~/.fakeed')
FAKEED_SQLITE_FILE = 'db.sqlite'
logger = logging.getLogger('tornado_proxy')

#logger.setLevel(logging.DEBUG)

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
    if proxy:
        logger.debug('Forward request via upstream proxy %s', proxy)
        tornado.httpclient.AsyncHTTPClient.configure(
            'tornado.curl_httpclient.CurlAsyncHTTPClient')
        host, port = parse_proxy(proxy)
        kwargs['proxy_host'] = host
        kwargs['proxy_port'] = port

    req = tornado.httpclient.HTTPRequest(url, **kwargs)
    client = tornado.httpclient.AsyncHTTPClient()
    client.fetch(req, callback)


class Torrent(Row):
    @property
    def id(self) -> int:
        return self.get('id')

    @property
    def info_hash(self) -> bytes:
        return self.get('info_hash')

    @info_hash.setter
    def info_hash(self, value: bytes):
        self['info_hash'] = value

    @property
    def peer_id(self) -> bytes:
        return self.get('peer_id')

    @peer_id.setter
    def peer_id(self, value: bytes):
        self['peer_id'] = value

    @property
    def netloc(self) -> str:
        return self.get('netloc')

    @netloc.setter
    def netloc(self, value : str):
        self['netloc'] = value

    @property
    def uploaded(self) -> int:
        return self.get('uploaded', 0)

    @uploaded.setter
    def uploaded(self, value: int):
        if not isinstance(value, int):
            raise Exception('bad argument')
        self['uploaded'] = value

    @property
    def downloaded(self) -> int:
        return self.get('downloaded', 0)

    @downloaded.setter
    def downloaded(self, value: int):
        if not isinstance(value, int):
            raise Exception('bad argument')
        self['downloaded'] = value

    @property
    def left(self) -> int:
        return self.get('left', 0)

    @left.setter
    def left(self, value: int):
        if not isinstance(value, int):
            raise Exception('bad argument')
        self['left'] = value

    @property
    def fake_uploaded(self) -> int:
        return self.get('fake_uploaded', 0)

    @fake_uploaded.setter
    def fake_uploaded(self, value: int):
        if not isinstance(value, int):
            raise Exception('bad argument')
        self['fake_uploaded'] = value

    @property
    def fake_downloaded(self) -> int:
        return self.get('fake_downloaded', 0)

    @fake_downloaded.setter
    def fake_downloaded(self, value: int):
        self['fake_downloaded'] = value

    @property
    def fake_left(self) -> int:
        return self.get('fake_left', 0)

    @fake_left.setter
    def fake_left(self, value: int):
        if not isinstance(value, int):
            raise Exception('bad argument')
        self['fake_left'] = value

    @property
    def ip(self) -> str:
        return self.get('ip')

    @ip.setter
    def ip(self, value: str):
        self['ip'] = value

    @property
    def event(self) -> str:
        return self.get('event')

    @event.setter
    def event(self, value: str):
        self['event'] = value

    @property
    def update_date(self) -> datetime:
        return self.get('update_date')

    @property
    def tracker_date(self) -> datetime:
        date = self.get('tracker_date')
        if date is None:
            date = datetime.now()
            self.tracker_date = date
        return date

    @tracker_date.setter
    def tracker_date(self, value: datetime):
        self['tracker_date'] = value



class TorrentDBConnection(Connection):
    def __init__(self, filename, isolation_level=None):
        super().__init__(filename, isolation_level)

    def query(self, query, *parameters, cls=Torrent):
        return super().query(query, *parameters, cls=cls)

    def get(self, torrent_id: int) -> Torrent:
        if isinstance(torrent_id, Torrent):
            torrent_id = torrent_id.id
        if torrent_id is None or not isinstance(torrent_id, int):
            return None
        for result in self.query('SELECT * FROM torrent WHERE id = ?', torrent_id):
            return result

    def getOrCreate(self, info_hash: bytes, peer_id: bytes, netloc: str) -> Torrent:
        for result in self.query('SELECT * FROM torrent WHERE info_hash = ? AND peer_id = ? AND netloc = ?',
                                 info_hash,
                                 peer_id,
                                 netloc):
            return result
        else:
            ret = Torrent()
            ret.info_hash = info_hash
            ret.peer_id = peer_id
            ret.netloc = netloc
            ret.tracker_date = datetime.now()
            return ret

    def save(self, torrent: Torrent):
        keys = torrent.keys()
        keys = [e for e in keys if e != 'id']
        query = 'INSERT INTO torrent('
        query += ', '.join(keys)
        query += ') '
        query += 'VALUES ('
        query += ', '.join(map(lambda key: '?', keys))
        query += ');'
        res = self.execute(query, *map(lambda k: torrent[k], keys))
        if isinstance(res, int):
            return self.get(res)

    def update(self, torrent: Torrent):
        if torrent is None or not isinstance(torrent.id, int):
            raise Exception("illegal argument")
        keys = torrent.keys()
        keys = [e for e in keys if e != 'id']
        query = 'UPDATE torrent SET '
        query += ', '.join(map(lambda t: '{0} = ?'.format(t), keys))
        query += ' WHERE id = %d' % torrent.id
        return self.execute(query, *map(lambda k: torrent[k], keys))

    def last_tracker_date(self, peer_id: bytes, netloc: str) -> datetime:
        query = "SELECT torrent.tracker_date as d " \
                "FROM torrent " \
                "WHERE tracker_date = " \
                "(SELECT MAX(t.tracker_date) FROM torrent as t WHERE t.peer_id = ? AND t.netloc = ?) LIMIT 1;"
        res = self.query(query, peer_id, netloc)
        if res:
            for result in res:
                return result['d']
        return datetime.now()




config = {
    'GLOBAL_MAX_UPLOAD': 200,  # limit the upload bandwidth in kByte / s at any time; set value to -1 to disable
    'CONSTANT_UPLOAD': 110,  # simulate a constant upload at this speed
    'MIN_RATIO': 0.75,  # the minimum ratio at any time (except if limited by GLOBAL_MAX_UPLOAD)
    'SECURE': True,  # use MIN_RATIO and CONSTANT_UPLOAD only if there is leechers
    'UPLOAD_FACTOR': 3.5  # multiply real uploaded bytes by this factor. (except if limited by GLOBAL_MAX_UPLOAD)
}


class UploadCalculator(object):
    """Compute an upload rate according to current date and config provided"""
    def __init__(self, db: TorrentDBConnection, config: dict):
        self.db = db
        self.config = config

    def __call__(self, torrent: Torrent, downloaded: int, uploaded: int) -> int:
        now = datetime.now()
        trackerdate = self.db.last_tracker_date(torrent.peer_id, torrent.netloc)
        timediff = now - trackerdate
        if trackerdate >= now or timediff > timedelta(days=1):  # seems a bad trackerdate
            return 0

        upload = 0.0
        second = timediff.total_seconds()

        is_secure = (not self.config.get('SECURE_MIN_RATIO', True)) or uploaded

        if is_secure:
            constant_upload = float(self.config.get('CONSTANT_UPLOAD', -1))
            if constant_upload > 0:
                upload += constant_upload * 1024 * second
            min_ratio = float(self.config.get('MIN_RATIO', 0))
            if min_ratio > 0:
                    upload += downloaded * min_ratio
        upload_factor = float(self.config.get('UPLOAD_FACTOR', -1))
        if upload_factor:
            upload += uploaded * upload_factor
        global_max_upload = float(self.config.get('GLOBAL_MAX_UPLOAD', -1))
        if global_max_upload >= 0:
            upload = max(upload, global_max_upload * 1024 * second)
        return int(upload)





class ProxyHandler(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.db = TorrentDBConnection(os.path.join(FAKEED_DIR, FAKEED_SQLITE_FILE))
        self.upcalc = UploadCalculator(self.db, config)

    SUPPORTED_METHODS = ['GET', 'POST', 'CONNECT']



    def get_byte_argument(self, name, default=tornado.web.RequestHandler._ARG_DEFAULT):
        ret = self.request.arguments.get(name, tornado.web.RequestHandler._ARG_DEFAULT)
        if ret is tornado.web.RequestHandler._ARG_DEFAULT:
            return default
        return ret[-1]


    @tornado.web.asynchronous
    def get(self):
        logger.debug('Handle %s request to %s', self.request.method,
                     self.request.uri)

        def handle_response(response):
            if response.error and not isinstance(response.error, tornado.httpclient.HTTPError):
                self.set_status(500)
                self.write('Internal server error:\n' + str(response.error))
            else:
                self.set_status(response.code)
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

                    uploaded_calc = self.upcalc(torrent, downloaded=downloaded, uploaded=uploaded)
                    uploaded_trick = max(uploaded, uploaded_calc)
                    logger.debug("new Up is %s", uploaded_trick)

                    # update internal database
                    torrent.tracker_date = datetime.now()
                    #TODO WORKER
                    if torrent.id is None:
                        self.db.save(torrent)
                    else:
                        self.db.update(torrent)
                    # let's replace uploaded into uri
                    uri = uri.replace('uploaded=%d' % uploaded, 'uploaded=%d' % uploaded_trick)
            # vodoo magic end here

            fetch_request(
                uri, handle_response,
                method=self.request.method, body=body,
                headers=self.request.headers, follow_redirects=False,
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
    if not os.path.exists(FAKEED_DIR):
        os.mkdir(FAKEED_DIR)
    fakeedfile = os.path.join(FAKEED_DIR, FAKEED_SQLITE_FILE)
    if not os.path.exists(fakeedfile):
        from create_sqlite_db import create_db
        create_db(fakeedfile, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'torrent.sql'))


if __name__ == '__main__':
    setup()
    port = os.environ.get('FAKEED_PORT')
    port = int(port) if port else 8888
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print("Starting HTTP proxy on port %d" % port)
    run_proxy(port)
