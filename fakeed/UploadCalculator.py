import configparser
from datetime import datetime, timedelta

from Torrent import Torrent, TorrentDBConnection


__author__ = 'maxisoft'


class UploadCalculator(object):
    """Compute an upload rate according to current date and config provided"""

    def __init__(self, db: TorrentDBConnection, config: configparser.RawConfigParser):
        self.db = db
        self.config = config['DEFAULT']

    def __call__(self, torrent: Torrent, downloaded: int, uploaded: int) -> int:
        now = datetime.now()
        trackerdate = self.db.last_tracker_date(torrent.peer_id, torrent.netloc)
        timediff = now - trackerdate
        if trackerdate >= now or timediff > timedelta(days=1):  # seems a bad trackerdate
            return 0

        upload = 0.0
        second = timediff.total_seconds()
        is_secure = (not self.config.getboolean('SECURE', True)) or uploaded

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
            upload = min(upload, global_max_upload * 1024 * second)
        return int(upload)

