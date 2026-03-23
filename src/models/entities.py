from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CatawikiCategory:
    """レーススケジュールマスタ情報を保持するデータクラス"""
    catawiki_cat_url: str
    catawiki_cat_url_lv: str
    catawiki_category_L0_id: int
    catawiki_category_L0_name: str
    catawiki_category_L0_url: str
    catawiki_category_L1_id: int
    catawiki_category_L1_name: str
    catawiki_category_L1_url: str
    catawiki_category_L2_id: int
    catawiki_category_L2_name: str
    catawiki_category_L2_url: str
    catawiki_auction_id: int
    catawiki_auction_name: str
    catawiki_auction_url: int
    last_get_date: datetime = field(default_factory=datetime.now)

    @property
    def upsert_sql(self):
        sql = """
            INSERT INTO
                wp_catawiki_category_master (
                    catawiki_cat_url,
                    catawiki_cat_url_lv,
                    catawiki_category_L0_id,
                    catawiki_category_L0_name,
                    catawiki_category_L0_url,
                    catawiki_category_L1_id,
                    catawiki_category_L1_name,
                    catawiki_category_L1_url,
                    catawiki_category_L2_id,
                    catawiki_category_L2_name,
                    catawiki_category_L2_url,
                    catawiki_auction_id,
                    catawiki_auction_name,
                    catawiki_auction_url,
                    last_get_date
                )
            VALUES (%(catawiki_cat_url)s, %(catawiki_cat_url_lv)s, %(catawiki_category_L0_id)s, %(catawiki_category_L0_name)s, %(catawiki_category_L0_url)s, %(catawiki_category_L1_id)s, %(catawiki_category_L1_name)s, %(catawiki_category_L1_url)s, %(catawiki_category_L2_id)s, %(catawiki_category_L2_name)s, %(catawiki_category_L2_url)s, %(catawiki_auction_id)s, %(catawiki_auction_name)s, %(catawiki_auction_url)s, %(last_get_date)s)
            ON DUPLICATE KEY UPDATE
                catawiki_cat_url=VALUES(catawiki_cat_url),
                catawiki_cat_url_lv=VALUES(catawiki_cat_url_lv),
                catawiki_category_L0_id=VALUES(catawiki_category_L0_id),
                catawiki_category_L0_name=VALUES(catawiki_category_L0_name),
                catawiki_category_L0_url=VALUES(catawiki_category_L0_url),
                catawiki_category_L1_id=VALUES(catawiki_category_L1_id),
                catawiki_category_L1_name=VALUES(catawiki_category_L1_name),
                catawiki_category_L1_url=VALUES(catawiki_category_L1_url),
                catawiki_category_L2_id=VALUES(catawiki_category_L2_id),
                catawiki_category_L2_name=VALUES(catawiki_category_L2_name),
                catawiki_category_L2_url=VALUES(catawiki_category_L2_url),
                catawiki_auction_id=VALUES(catawiki_auction_id),
                catawiki_auction_name=VALUES(catawiki_auction_name),
                catawiki_auction_url=VALUES(catawiki_auction_url);
            """.strip().replace("''", "NULL")
        return sql


@dataclass
class CatawikiList:
    catawiki_cat_url: str
    item_url: str
    item_img_url: str
    item_title: str
    create_date: datetime = field(default_factory=datetime.now)
    update_date: datetime = field(default_factory=datetime.now)

    @property
    def upsert_sql(self):
        sql = """
            INSERT INTO
                wp_catawiki_data_list (
                    catawiki_cat_url,
                    item_url,
                    item_img_url,
                    item_title,
                    create_date,
                    update_date
                )
            VALUES (%(catawiki_cat_url)s, %(item_url)s, %(item_img_url)s, %(item_title)s, %(create_date)s, %(update_date)s)
            ON DUPLICATE KEY UPDATE 
                catawiki_cat_url=VALUES(catawiki_cat_url),
                item_img_url=VALUES(item_img_url),
                item_title=VALUES(item_title),
                update_date=VALUES(update_date);
            """.strip().replace("''", "NULL")
        return sql


@dataclass
class CatawikiWinningBid:
    item_url: str
    bidding_end_time: datetime
    bidding_start_time: datetime
    close_at: datetime | None
    closed_at: datetime | None
    auction_id: int
    auction_name: str
    auction_theme: str
    auction_theme_id: int
    auction_type_family_id: int
    auction_type_family_name: str
    auction_type_id: int
    category_L0_id: int
    category_L0_name: str
    category_L1_id: int
    category_L1_name: str
    category_L2_id: int
    category_L2_name: str
    lot_id: int
    is_closed: int
    is_sold: int
    current_bid_amount: int
    price_currency: str
    reserve_price_met: int | None
    sellerInfo_id: int
    sellerInfo_url: str
    sellerInfo_address_country_name: str
    not_found: int = 0
    create_date: datetime = field(default_factory=datetime.now)

    @property
    def upsert_sql(self):
        sql = """
            INSERT INTO
                wp_catawiki_data_winning (
                    item_url,
                    bidding_end_time,
                    bidding_start_time,
                    close_at,
                    closed_at,
                    auction_id,
                    auction_name,
                    auction_theme,
                    auction_theme_id,
                    auction_type_family_id,
                    auction_type_family_name,
                    auction_type_id,
                    category_L0_id,
                    category_L0_name,
                    category_L1_id,
                    category_L1_name,
                    category_L2_id,
                    category_L2_name,
                    lot_id,
                    is_closed,
                    is_sold,
                    current_bid_amount,
                    price_currency,
                    reserve_price_met,
                    sellerInfo_id,
                    sellerInfo_url,
                    sellerInfo_address_country_name,
                    not_found,
                    create_date
                )
            VALUES (%(item_url)s, %(bidding_end_time)s, %(bidding_start_time)s, %(close_at)s, %(closed_at)s, %(auction_id)s, %(auction_name)s, %(auction_theme)s, %(auction_theme_id)s, %(auction_type_family_id)s, %(auction_type_family_name)s, %(auction_type_id)s, %(category_L0_id)s, %(category_L0_name)s, %(category_L1_id)s, %(category_L1_name)s, %(category_L2_id)s, %(category_L2_name)s, %(lot_id)s, %(is_closed)s, %(is_sold)s, %(current_bid_amount)s, %(price_currency)s, %(reserve_price_met)s, %(sellerInfo_id)s, %(sellerInfo_url)s, %(sellerInfo_address_country_name)s, %(not_found)s, %(create_date)s)
            ON DUPLICATE KEY UPDATE
                bidding_end_time=VALUES(bidding_end_time),
                bidding_start_time=VALUES(bidding_start_time),
                close_at=VALUES(close_at),
                closed_at=VALUES(closed_at),
                auction_id=VALUES(auction_id),
                auction_name=VALUES(auction_name),
                auction_theme=VALUES(auction_theme),
                auction_theme_id=VALUES(auction_theme_id),
                auction_type_family_id=VALUES(auction_type_family_id),
                auction_type_family_name=VALUES(auction_type_family_name),
                auction_type_id=VALUES(auction_type_id),
                category_L0_id=VALUES(category_L0_id),
                category_L0_name=VALUES(category_L0_name),
                category_L1_id=VALUES(category_L1_id),
                category_L1_name=VALUES(category_L1_name),
                category_L2_id=VALUES(category_L2_id),
                category_L2_name=VALUES(category_L2_name),
                lot_id=VALUES(lot_id),
                is_closed=VALUES(is_closed),
                is_sold=VALUES(is_sold),
                current_bid_amount=VALUES(current_bid_amount),
                price_currency=VALUES(price_currency),
                reserve_price_met=VALUES(reserve_price_met),
                sellerInfo_id=VALUES(sellerInfo_id),
                sellerInfo_url=VALUES(sellerInfo_url),
                sellerInfo_address_country_name=VALUES(sellerInfo_address_country_name),
                not_found=VALUES(not_found),
                create_date=VALUES(create_date);
            """.strip().replace("''", "NULL")
        return sql


@dataclass
class NotFoundWinningBid:
    item_url: str
    not_found: int = 0
    create_date: datetime = field(default_factory=datetime.now)

    @property
    def upsert_sql(self):
        sql = """
            INSERT INTO
                wp_catawiki_data_winning (
                    item_url,
                    not_found,
                    create_date
                )
            VALUES (%(item_url)s, %(not_found)s, %(create_date)s)
            ON DUPLICATE KEY UPDATE
                not_found=VALUES(not_found),
                create_date=VALUES(create_date);
            """.strip().replace("''", "NULL")
        return sql


class PageLoadeException(Exception):
    """ページの読み込みに失敗した場合の例外クラス"""
    pass
