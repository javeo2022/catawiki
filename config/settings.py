from datetime import date


class Config:
    # --- EPARK関連 ---
    DOMAIN: str = "https://epark.jp/"
    URL: str = "https://www.catawiki.com/en"
    # sqliteで作成するdb名
    db_name: str = "epark_sekkotsu-seitai.db"
    # loggerのinfo
    exc_info: bool = False

config = Config()
