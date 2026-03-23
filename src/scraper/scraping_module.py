from dataclasses import asdict
from datetime import datetime, timedelta
import logging

from selenium.webdriver.support import expected_conditions as EC
from src.lib.selenium_wrapper import SeleniumWrapper
from src.database.xserver_connector import DatabaseManager
from src.models.entities import PageLoadeException
from src.parsers.catawiki_parser import get_max_page_no, list_page_parse, winning_page_parse
from src.utils.common import update_query_param
from urllib.parse import urlencode


class CatawikiScraper(SeleniumWrapper):
    """catawikiをスクレイピングするクラス"""
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.start_time = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

    def close(self):
        self.db.close()
        self.driver_close()

    def scraping_list(self):
        category_urls = self.get_category_list()
        _ = self.get_list_data(category_urls=category_urls)

    def scraping_winning_bid(self):
        _ = self.get_winning_bid_data()

    def get_category_list(self) -> list[str]:
        sql = """
            SELECT DISTINCT catawiki_cat_url
            FROM wp_catawiki_category_master
            WHERE catawiki_cat_url_lv='lv1'
            AND last_get_date<DATE_ADD(CURRENT_TIMESTAMP(), INTERVAL -3 HOUR);
        """.strip()
        rows = self.db.fetch(sql)
        category_urls = [row["catawiki_cat_url"] for row in rows]
        return category_urls

    def get_sub_category_list(self, category_url: str) -> list[str]:
        sql = f"""
            SELECT DISTINCT catawiki_cat_url
            FROM wp_catawiki_category_master
            WHERE catawiki_cat_url_lv='lv2'
            AND catawiki_category_L1_url='{category_url}'
            AND last_get_date<DATE_ADD(CURRENT_TIMESTAMP(), INTERVAL -3 HOUR);
        """.strip()
        rows = self.db.fetch(sql)
        sub_category_urls = [row["catawiki_cat_url"] for row in rows]
        return sub_category_urls

    def get_list_data(self, category_urls: list[str]):
        for url in category_urls:
            self.driver_open(enable_js=False, imagesEnabled=False)  # カテゴリーページはJavaScriptを使用していないため、JSと画像は無効化して高速化する
            self.selenium_page_load(url=url)
            _ = self.selenium_click('#cookie_bar_agree_button > span.c-button__overlay.c-button__overlay--primary', timeout=3)  # クッキー同意のポップアップを閉じる
            max_page_no = get_max_page_no(markup=self.driver.page_source)
            # ページ数が100を超える場合はサブカテゴリーに掘り下げてクロールする
            if max_page_no > 100:
                logging.info(f'カテゴリーページURL:{url} のページ数が100を超えています。サブカテゴリーに掘り下げてクロールします。最大ページ数:{max_page_no}')
                sub_category_urls = self.get_sub_category_list(category_url=url)
                for sub_url in sub_category_urls:
                    self.selenium_page_load(url=sub_url)
                    sub_max_page_no = get_max_page_no(markup=self.driver.page_source)
                    if sub_max_page_no > 100:
                        logging.warning(f'サブカテゴリーページURL:{sub_url} のページ数も100を超えています。締切日で分割してクロールします。最大ページ数:{sub_max_page_no}')                        
                        for days in range(7):
                            target_date = (datetime.now() + timedelta(days=days)).strftime('%Y%m%d')
                            encoded_key = urlencode("filters[bidding_end_days][]").replace("%", "%25")
                            days_url = update_query_param(sub_url, encoded_key, target_date)
                            self.selenium_page_load(url=days_url)
                            dys_max_page_no = get_max_page_no(markup=self.driver.page_source)
                            logging.info(f'サブカテゴリーページURL:{days_url} をクロールします。最大ページ数:{dys_max_page_no}')
                            self.crawling_list_page(url=days_url, max_page_no=int(dys_max_page_no))
                    else:
                        logging.info(f'サブカテゴリーページURL:{sub_url} をクロールします。最大ページ数:{sub_max_page_no}')
                        self.crawling_list_page(url=sub_url, max_page_no=int(sub_max_page_no))
                        logging.info(f'サブカテゴリーページURL:{sub_url} のクロールが完了しました。')
            else:
                logging.info(f'カテゴリーページURL:{url} をクロールします。最大ページ数:{max_page_no}')
                self.crawling_list_page(url=url, max_page_no=int(max_page_no))

            # カテゴリーページの最終更新日時を更新する
            sql = """
                UPDATE wp_catawiki_category_master
                SET last_get_date=CURRENT_TIMESTAMP
                WHERE catawiki_category_L1_url=%s;
            """.strip()
            self.db.execute(sql=sql, params=(url,))
            logging.info(f'カテゴリーページURL:{url} のクロールが完了しました。')
            self.driver_close()
        self.driver_close()

    def crawling_list_page(self, url: str, max_page_no: int):
        for page_no in range(1, max_page_no + 1):
            page_url = update_query_param(url, 'page', str(page_no))
            # ページ遷移する※たまに白紙ページで止まるので3回までリロードする
            for _ in range(3):
                if self.selenium_page_load(url=page_url):
                    break
                logging.info(f'ページ読み込みエラーのためリロードします URL:{url}')
            else:
                # 商品ページがない時の分岐
                if page_no == 1:
                    logging.info(f"オークション商品がありませんでした URL:{url}")
                    return
                else:
                    raise PageLoadeException(f'ページが読み込めませんでした URL:{page_url}')                
            list_data = list_page_parse(catawiki_cat_url=url, markup=self.driver.page_source)
            # ここでlist_dataをDBに保存する処理を書く
            if list_data:
                self.db.executemany(sql=list_data[0].upsert_sql, params=[asdict(data) for data in list_data])
            # ページ数が100を超える場合は一旦ループを抜ける（catawiki仕様）
            if page_no > 100:
                logging.warning(f'ページ数が100を超えました。URL:{url} ページ数:{page_no}')
                break

    def get_winning_bid_data(self, sort_order: str = "asc"):
        sql = f"""
            SELECT
                l.item_url
            FROM
                wp_catawiki_data_list l
                INNER JOIN wp_catawiki_category_master c
                ON l.catawiki_cat_url=c.catawiki_cat_url
                LEFT JOIN wp_catawiki_data_winning w
                ON l.item_url=w.item_url
            WHERE 
                c.last_get_date>'{self.start_time}'
                AND l.update_date<'{self.start_time}'
                AND ((w.is_closed=0 AND bidding_end_time<CURDATE()) OR w.is_closed IS NULL)
                AND (w.not_found=0 OR w.not_found IS NULL)
            ORDER BY
                l.update_date {sort_order}
        """.strip()
        rows = self.db.fetch(sql)
        item_urls = [row["item_url"] for row in rows]
        self.driver_open(enable_js=False, imagesEnabled=False)  # 落札ページはJavaScriptを使用していないため、JSと画像は無効化して高速化する
        for i, url in enumerate(item_urls, start=1):
            # ページ遷移する※たまに白紙ページで止まるので3回までリロードする
            for _ in range(3):
                ec =EC.presence_of_element_located(('css selector', '#__NEXT_DATA__'))
                if self.selenium_page_load(url=url, condition=ec):
                    break
                logging.info(f'ページ読み込みエラーのためリロードします URL:{url}')
            else:
                logging.error(f'ページが読み込めませんでした URL:{url}')
                continue

            try:
                data = winning_page_parse(item_url=url, markup=self.driver.page_source)
            except Exception as e:
                logging.error(f'落札ページの解析に失敗しました URL:{url} エラー内容:{e}')
                continue
            if data:
                for _ in range(3):
                    try:
                        # クエリ実行
                        self.db.execute(data.upsert_sql, asdict(data))
                        break
                    except (self.db.mysql.connector.Error, Exception) as e:
                        # 接続が切れた場合のみ再接続を試みる
                        print("DB接続が切断されたため再接続を試みます")
                        self.db.reconnect() 

            if i % 10 == 0:
                logging.info(f'落札ページのクロール進捗: {i}/{len(item_urls)} 件')
        self.driver_close()
