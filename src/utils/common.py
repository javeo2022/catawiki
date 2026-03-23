import logging
import time
import re
from datetime import datetime, date, timedelta
from typing import Optional, Any
from dateutil.relativedelta import relativedelta
import urllib.parse

# 必要に応じて config/settings.py から読み込むように書き換えてください
# from config import settings


class ScrapeError(Exception):
    """スクレイピング中に発生したカスタムエラー"""
    pass


def setup_logging(log_level: str = "INFO", log_file_path: str = "scraper.log"):
    """ログ設定を初期化する"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def safe_cast(value: Any, to_type: type, default: Optional[Any] = None) -> Any:
    """
    値を安全に指定された型にキャストする。キャストできない場合はデフォルト値を返す。
    """
    if value is None:
        return default
    try:
        return to_type(value)
    except (ValueError, TypeError):
        return default


def parse_date_str(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[date]:
    """
    日付文字列をdateオブジェクトにパースする。
    """
    try:
        return datetime.strptime(date_str, fmt).date()
    except ValueError:
        return None


def parse_time_string(time_str: str, default: timedelta = timedelta(seconds=0)) -> timedelta:
    """分:秒.ミリ秒 または 秒.ミリ秒 を timedelta に変換"""
    try:
        if ":" in time_str:
            minutes, sec_ms = time_str.split(":")
            seconds = float(sec_ms)
            return timedelta(minutes=int(minutes), seconds=seconds)
        else:
            seconds = float(time_str)
            return timedelta(seconds=seconds)
    except Exception:
        return default


def timedelta_to_str(td: timedelta) -> str:
    """timedeltaを '分:秒.ミリ秒' 形式の文字列に変換"""
    try:
        total_seconds = td.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        if minutes == 0 and seconds == 0:
            return ""
        else:
            return f"{minutes}:{seconds:04.1f}"
    except Exception:
        return ""


def get_query_param(url: str, key: str, default: str = "") -> str:
    """指定したURLからクエリパラメータを取得"""
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    return query_params.get(key, [default])[0]


def update_query_param(url, key, new_val):
    pr = urllib.parse.urlparse(url)
    d = urllib.parse.parse_qs(pr.query)
    d[key] = new_val
    return urllib.parse.urlunparse(pr._replace(query=urllib.parse.urlencode(d, doseq=True)))


def can_convert_to_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def apply_delay(delay_sec: float = 1.0):
    """スクレイピング間の遅延を適用する"""
    time.sleep(delay_sec)


def month_range(start: datetime, stop: datetime, step=relativedelta(month=1)):
    """日付の範囲を取得するジェネレータ"""
    current: datetime = start
    while current <= stop:
        yield current
        current += step


def get_regular_holidays(text):
    # 曜日の定義
    ORDER = ["月", "火", "水", "木", "金", "土", "日"]
    ALL_DAYS = set(ORDER)
    WEEKDAYS = {"月", "火", "水", "木", "金"}
    
    # 1. [] で囲まれた部分の中身を「すべて」抽出する
    # re.findall はマッチした部分をリストで返します（例: ['平日', '土・日・祝']）
    matches = re.findall(r"\[(.*?)\]", text)
    
    # 見つかった中身をすべて結合して1つの文字列にする
    # 例: "平日" + "土・日・祝" = "平日土・日・祝"
    target_text = "".join(matches)

    # [] が全く見つからない場合は、営業日指定なしとみなす
    # （サイトの仕様に合わせて「定休日なし」にするか「全休」にするか調整が必要ですが、
    #   ここでは記述がない＝営業日が取得できない＝全日が定休日（営業日なし）として扱います）
    if not target_text:
        return list(ORDER) # 全て定休日として返す

    # 2. 「全日」や「無休」が含まれている場合は、定休日なし
    if "全日" in target_text or "無休" in target_text:
        return []

    # 営業曜日を格納するセット
    business_days = set()

    # 3. 「平日」が含まれている場合の処理
    if "平日" in target_text:
        business_days.update(WEEKDAYS)
        # 「平日」という文字を消去（「日」の誤判定防止）
        target_text = target_text.replace("平日", "")

    # 4. 結合したテキストから個別の曜日を探す
    found_individual_days = set(re.findall(r"[月火水木金土日]", target_text))
    business_days.update(found_individual_days)
    
    # 5. 全曜日から営業曜日を差し引く（差集合）
    holidays = ALL_DAYS - business_days
    
    # 6. 曜日の順序を整えてリスト化
    sorted_holidays = [day for day in ORDER if day in holidays]
    
    return sorted_holidays
'''
import pandas as pd

def search_postcode_offline(address_csv, target_address):
    # 1. 郵便番号データの読み込み
    # 日本郵便のCSVは Shift-JIS なのでエンコーディングを指定
    # 2列目が郵便番号、6,7,8列目が住所（都道府県、市区町村、町域）
    cols = [2, 6, 7, 8]
    names = ['zipcode', 'pref', 'city', 'town']
    
    df = pd.read_csv(address_csv, encoding='shift_jis', header=None, 
                     usecols=cols, names=names, dtype={'zipcode': str})

    # 2. 住所を結合してフル住所カラムを作成
    df['full_address'] = df['pref'] + df['city'] + df['town']

    # 3. 検索 (入力された住所が含まれている行を抽出)
    # 例: "東京都新宿区西新宿" で検索
    result = df[df['full_address'].str.contains(target_address)]

    return result[['zipcode', 'full_address']]

# 実行例
csv_file = 'KEN_ALL.CSV'
search_word = "東京都新宿区西新宿"
results = search_postcode_offline(csv_file, search_word)

print(f"--- '{search_word}' の検索結果 ---")
print(results)
'''