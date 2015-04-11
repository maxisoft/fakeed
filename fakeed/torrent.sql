/*
Navicat SQLite Data Transfer

Source Server         : fakeed
Source Server Version : 30714
Source Host           : :0

Target Server Type    : SQLite
Target Server Version : 30714
File Encoding         : 65001

Date: 2015-04-11 09:14:07
*/

PRAGMA foreign_keys = OFF;

-- ----------------------------
-- Table structure for torrent
-- ----------------------------
DROP TABLE IF EXISTS "main"."torrent";
CREATE TABLE "torrent" (
  "id"              INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  "info_hash"       BLOB                              NOT NULL,
  "peer_id"         BLOB                              NOT NULL,
  "netloc"          TEXT                              NOT NULL,
  "uploaded"        INTEGER,
  "downloaded"      INTEGER,
  "left"            INTEGER,
  "fake_uploaded"   INTEGER,
  "fake_downloaded" INTEGER,
  "fake_left"       INTEGER,
  "ip"              TEXT,
  "event"           TEXT,
  "update_date"     TIMESTAMP,
  "tracker_date"    TIMESTAMP
);

-- ----------------------------
-- Indexes structure for table torrent
-- ----------------------------
CREATE UNIQUE INDEX "main"."idx_info_hash_peer_id_netloc"
ON "torrent" ("info_hash" ASC, "peer_id" ASC, "netloc" ASC);

-- ----------------------------
-- Triggers structure for table torrent
-- ----------------------------
DROP TRIGGER IF EXISTS "main"."UPDATE_DATE_INSERT_ TRIGGER";
CREATE TRIGGER "UPDATE_DATE_INSERT_ TRIGGER" AFTER INSERT ON "torrent"
BEGIN
  UPDATE torrent
  SET update_date = datetime('now')
  WHERE id = new.id;
END;
;
DROP TRIGGER IF EXISTS "main"."UPDATE_DATE_UPDATE_ TRIGGER";
CREATE TRIGGER "UPDATE_DATE_UPDATE_ TRIGGER" AFTER UPDATE ON "torrent"
BEGIN
  UPDATE torrent
  SET update_date = datetime('now')
  WHERE id = new.id;
END;
;
