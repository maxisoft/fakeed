#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import sys

if sys.version_info[0] == 2:
    from itertools import imap as map
    from itertools import izip as zip


class Row(dict):
    """A dict that allows for object-like property access syntax."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class Connection(object):
    """
    A lightweight wrapper around sqlite3; based on tornado.database
    
    db = sqlite.Connection("filename")
    for article in db.query("SELECT * FROM articles")
        print article.title
      
    Cursors are hidden by the implementation.

    By SerhoLiu: https://github.com/SerhoLiu/serholiu.com/blob/master/miniakio/libs/sqlite3lib.py
    """

    def __init__(self, filename, isolation_level=None):
        self.filename = filename
        self.isolation_level = isolation_level  # None = autocommit
        self._db = None
        try:
            self.reconnect()
        except:
            # log error @@@
            raise

    def close(self):
        """Close database connection"""
        if getattr(self, "_db", None) is not None:
            self._db.close()
        self._db = None

    def reconnect(self):
        """Closes the existing database connection and re-opens it."""
        self.close()
        self._db = sqlite3.connect(self.filename, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self._db.isolation_level = self.isolation_level

    def _cursor(self):
        """Returns the cursor; reconnects if disconnected."""
        if self._db is None:
            self.reconnect()
        return self._db.cursor()

    def __del__(self):
        self.close()

    def execute(self, query, *parameters):
        """Executes the given query, returning the lastrowid from the query."""
        cursor = self._cursor()
        try:
            self._execute(cursor, query, parameters)
            return cursor.lastrowid
        finally:
            pass

    def executemany(self, query, parameters):
        """Executes the given query against all the given param sequences"""
        cursor = self._cursor()
        try:
            cursor.executemany(query, parameters)
            return cursor.lastrowid
        finally:
            cursor.close()

    def _execute(self, cursor, query, parameters):
        try:
            return cursor.execute(query, parameters)
        except OperationalError:
            # log error @@@
            self.close()
            raise


    def query(self, query, *parameters, cls=Row):
        """Returns a row list for the given query and parameters."""
        cursor = self._cursor()
        self._execute(cursor, query, parameters)
        column_names = [d[0] for d in cursor.description]
        return map(lambda row: cls(zip(column_names, row)), cursor)


OperationalError = sqlite3.OperationalError