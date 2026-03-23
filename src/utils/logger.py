import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime


# 定数設定
LOG_DIR = "logs"
LOG_FILE_NAME = "scraper.log"
MAX_BYTES = 10 * 1024 * 1024  # 10MBごとにローテーション
BACKUP_COUNT = 5              # 過去ログを5世代残す
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(funcName)s() : %(message)s"


def get_logger(name: str = __name__) -> logging.Logger:
    """
    指定された名前のロガーを取得または作成して返す。
    シングルトン的に動作し、ハンドラの重複登録を防ぐ。
    """
    logger = logging.getLogger(name)

    # 既にハンドラが設定されている場合は、設定済みのloggerを返して終了
    # (これにより、モジュールごとにimportしてもログが二重に出ない)
    if logger.hasHandlers():
        return logger

    logger.setLevel(DEFAULT_LOG_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT)

    # ------------------------------------------------
    # 1. コンソール出力用ハンドラ (標準出力)
    # ------------------------------------------------
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # ------------------------------------------------
    # 2. ファイル出力用ハンドラ (ローテーション付き)
    # ------------------------------------------------
    # ログディレクトリの作成
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    file_path = os.path.join(LOG_DIR, LOG_FILE_NAME)

    # RotatingFileHandler: 指定サイズを超えたらバックアップを作成
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ライブラリ(urllib3, selenium等)のログがうるさい場合はレベルを上げる
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)

    return logger


def set_log_level(level: int):
    """
    実行時にログレベルを変更するための関数
    Ex: set_log_level(logging.DEBUG)
    """
    logging.getLogger().setLevel(level)


# テスト実行用
if __name__ == "__main__":
    lg = get_logger("test_logger")
    lg.info("これはINFOログです")
    lg.debug("これはDEBUGログです（デフォルトでは出ません）")
    lg.warning("これはWARNINGログです")
    lg.error("これはERRORログです")

    # レベル変更テスト
    set_log_level(logging.DEBUG)
    lg.debug("レベル変更後のDEBUGログです")
