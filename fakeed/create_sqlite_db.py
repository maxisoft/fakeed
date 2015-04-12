#!/usr/bin/env python3

__author__ = 'maxime'
import sqlite3

DEFAULT_FAKEED_SQLITE_PATH = 'db.sqlite'


def create_db(db_path=DEFAULT_FAKEED_SQLITE_PATH, sql_file='torrent.sql'):
    with sqlite3.connect(db_path) as conn:
        curr = conn.cursor()
        with open(sql_file) as sql:
            curr.executescript(sql.read())
        conn.commit()
    return True


if __name__ == '__main__':
    import sys
    import os

    if not '-y' in sys.argv:
        try:
            input(
                """WARNING THIS TOOL WILL ERASE ANY EXISTING FAKEED DB IN CURRENT PATH.
                PRESS CTRL+C TO CANCEL OR HIT ENTER TO CONTINUE...\n""")
        except KeyboardInterrupt:
            sys.exit()
        if os.path.exists(DEFAULT_FAKEED_SQLITE_PATH):
            os.remove(DEFAULT_FAKEED_SQLITE_PATH)
    create_db()
    print('database created at {}'.format(os.path.abspath(DEFAULT_FAKEED_SQLITE_PATH)))