# -*- coding: utf-8 -*-
from pathlib import Path
from dotenv import load_dotenv
import os
import mysql.connector
from sshtunnel import SSHTunnelForwarder
import logging


# 外部ライブラリのログレベルを一括でWARNING以上に引き上げる
for lib in ['sshtunnel', 'paramiko', 'mysql.connector', 'mysql.connector.plugins']:
    logging.getLogger(lib).setLevel(logging.WARNING)

# .envファイルを読み込む
base_path = Path(__file__).parent
env_path = base_path / '.env'
key_path = base_path / 'key/xs687391.key'
load_dotenv(dotenv_path=env_path)


class DatabaseManager:
    def __init__(self):
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_name = os.getenv("DB_NAME")
        self.db_host = os.getenv("DB_HOST", '127.0.0.1')
        self.db_port = int(os.getenv("DB_PORT"))
        self.db_charset = os.getenv("DB_CHARSET")

        self.ssh_host = os.getenv("SSH_HOST")
        self.ssh_port = int(os.getenv("SSH_PORT"))
        self.ssh_user = os.getenv("SSH_USER")
        self.ssh_password = os.getenv("SSH_PASSWORD")
        self.ssh_pkey = key_path._str if key_path.exists() else os.getenv("SSH_PKEY")

        self.server = None
        self.con = None
        self.cur = None
        self.__connect__()

    def __connect__(self):
        self.server = SSHTunnelForwarder(
            (self.ssh_host, self.ssh_port),
            ssh_username=self.ssh_user,
            ssh_password=self.ssh_password,
            ssh_pkey=self.ssh_pkey,
            remote_bind_address=(self.db_host, self.db_port),
        )
        self.server.start()
        # connectのリファレンスはコチラ
        # https://dev.mysql.com/doc/connector-python/en/connector-python-connectargs.html
        self.con = mysql.connector.connect(
            host=self.db_host,
            port=self.server.local_bind_port,
            user=self.db_user,
            passwd=self.db_password,
            db=self.db_name,
            charset=self.db_charset,
            use_pure=True,
        )
        # 扱いやすいdict型を指定しておく
        self.cur = self.con.cursor(dictionary=True)

    def __disconnect__(self):
        if self.cur:
            self.cur.close()
        if self.con:
            self.con.close()
        if self.server:
            self.server.stop()

    def _ensure_cursor(self):
        """SSHトンネルとMySQL接続を両方チェックし、必要なら再構築する。"""
        # 1. SSHトンネル自体が生きてるか確認（ssh_tunnel はインスタンス変数と仮定）
        if not self.server.is_active:
            print("SSHトンネルが切断されています。トンネルを再起動します...")
            self.server.restart()
            # トンネルを再起動したら、MySQL接続も作り直すべき
            self.__connect__() 
            return

        # 2. MySQL接続のチェック
        try:
            self.con.ping(reconnect=True, delay=2, attempts=3)
        except Exception:
            # pingでダメなら強制的に再接続
            self.__connect__()
        
        # 3. カーソルの再作成（常に最新にする）
        self.cur = self.con.cursor(dictionary=True)

    def fetch(self, sql, params=None):
        self._ensure_cursor()
        self.cur.execute(sql, params)
        return self.cur.fetchall()

    def execute(self, sql, params=None, commit: bool = True):
        self._ensure_cursor()
        if params:
            self.cur.execute(operation=sql, params=params)
        else:
            self.cur.execute(operation=sql)
        if commit:
            self.con.commit()

    def executemany(self, sql, params, commit: bool = True):
        self._ensure_cursor()
        self.cur.executemany(operation=sql, seq_params=params)
        if commit:
            self.con.commit()

    def procedure(self, proc_name):
        self._ensure_cursor()
        self.cur.callproc(proc_name)
        self.con.commit()

    def open(self):
        self.__connect__()

    def close(self):
        self.__disconnect__()