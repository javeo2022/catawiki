from dataclasses import asdict
import logging

from bs4 import BeautifulSoup
import copy
from time import sleep

from config.settings import config
from src.lib.selenium_wrapper import SeleniumWrapper
from src.database.xserver_connector import DatabaseManager
from src.models.entities import CatawikiCategory
from src.utils.common import get_query_param

class CatawikiScraper(SeleniumWrapper):
    """catawikiをスクレイピングするクラス"""
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()

    def close(self):
        self.db.close()
        self.driver_close()

    def scraping_list(self):
        category_data_list = self.get_category_list()
        _ = self.get_subcategory(category_data_list=category_data_list)

    def get_category_list(self) -> list[CatawikiCategory]:
        sql = """
            SELECT *
            FROM wp_catawiki_category_master
            WHERE catawiki_cat_url_lv = 'lv1'
        """.strip()
        rows = self.db.fetch(sql)
        category_data_list = [CatawikiCategory(**row) for row in rows]
        return category_data_list

    def get_subcategory(self, category_data_list: list[CatawikiCategory]):
        self.driver_open()
        self.selenium_page_load(config.URL)
        _ = self.selenium_click('#cookie_bar_agree_button > span.c-button__overlay.c-button__overlay--primary', timeout=3)  # クッキー同意のポップアップを閉じる
        for category in category_data_list:
            self.selenium_page_load(category.catawiki_cat_url)
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            subcategory_list = [subcategory.get_text(strip=True) for subcategory in soup.select('ul[data-testid="l2-category-list"] > li')]
            for sg in subcategory_list:
                self.selenium_page_load(category.catawiki_cat_url)
                btn = self.selenium_find_text_element('ul[data-testid="l2-category-list"] > li', sg)
                self.selenium_click(btn)
                # サブカテゴリーのIDはURLのクエリパラメータから取得する
                id_ = ''
                while id_ == '':
                    sleep(0.5)
                    id_ = get_query_param(self.driver.current_url, "l2_categories")
                sub = copy.copy(category)
                sub.catawiki_cat_url = self.driver.current_url
                sub.catawiki_cat_url_lv = "lv2"
                sub.catawiki_category_L2_name = sg
                sub.catawiki_category_L2_id = id_
                sub.catawiki_category_L2_url = self.driver.current_url
                self.db.execute(sub.upsert_sql, asdict(sub))
        self.driver_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = CatawikiScraper()
    try:
        scraper.scraping_list()
    except Exception as e:
        logging.error(f"Error occurred: {e}")
    finally:
        scraper.close()