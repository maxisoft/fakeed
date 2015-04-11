__author__ = 'maxime'
import random

from proxy import Torrent, TorrentDBConnection


conn = TorrentDBConnection('db.sqlite')
torrent = Torrent()
torrent.peer_id = b"3" + bytes(random.randint(1, 500))
torrent.info_hash = b"5"

tor1 = conn.save(torrent)
tor1.uploaded = 3
print(conn.update(tor1))
print(conn.get(1))