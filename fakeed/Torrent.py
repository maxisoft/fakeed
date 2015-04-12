__author__ = 'maxisoft'

from SqlTool import Row
from datetime import datetime
from SqlTool import Connection


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
