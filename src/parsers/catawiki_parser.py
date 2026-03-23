import json
from typing import Union
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from src.models.entities import CatawikiList, CatawikiWinningBid, NotFoundWinningBid
from src.utils.soup_helper import get_element_attribute_or_text


def get_max_page_no(markup: str) -> int:
    soup = BeautifulSoup(markup=markup, features="lxml")
    max_page_no = get_element_attribute_or_text(soup_object=soup,
                                                selector='nav.c-pagination__container > div.c-pagination__pages > span.c-pagination__page',
                                                index=-1,
                                                default="1",
                                                )
    return int(max_page_no)


def list_page_parse(catawiki_cat_url: str, markup: str) -> list[CatawikiList]:
    soup = BeautifulSoup(markup=markup, features="lxml")
    list_data = []
    for card in soup.select('div[data-sentry-component="LotList"] > div[data-sentry-component="ListingLotsWrapper"]'):
        item_url = get_element_attribute_or_text(soup_object=card, selector="a.c-lot-card", attribute="href")
        item_img_url = get_element_attribute_or_text(soup_object=card, selector="img.c-lot-card__image-element", attribute="src")
        item_title = get_element_attribute_or_text(soup_object=card, selector="p.c-lot-card__title")
        list_data.append(
            CatawikiList(
                catawiki_cat_url=catawiki_cat_url,
                item_url=item_url,
                item_img_url=item_img_url,
                item_title=item_title,
            )
        )
    return list_data


def winning_page_parse(item_url: str, markup: str) -> Union[CatawikiWinningBid, NotFoundWinningBid, None]:
    soup = BeautifulSoup(markup=markup, features="lxml")
    # __NEXT_DATA__ タグを取得
    script_tag = soup.select_one('#__NEXT_DATA__')
    if not script_tag:
        raise ValueError("Could not find __NEXT_DATA__ script tag.")

    data = json.loads(script_tag.string)

    # ページが見つからない場合の処理
    if data["page"] == '/404':
        return NotFoundWinningBid(
            item_url=item_url,
            not_found=1,
            create_date=datetime.now()
        )

    # 階層が深いため各パーツを抽出
    props = data['props']['pageProps']
    dl = props['dataLayerBase']
    auction = props['auction']
    bidding = props['biddingBlockResponse']
    lotDetailsData = props['lotDetailsData']
    sellerInfo = lotDetailsData['sellerInfo']

    # 文字列からdatetimeへの変換（ISO形式を想定）
    def _to_dt(s: str) -> datetime:
        if s.endswith('Z'):
            utc_dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        else:
            utc_dt = datetime.fromisoformat(s)
        # 3. 日本時間のタイムゾーン（UTC+9）を定義
        jst_tz = timezone(timedelta(hours=9))
        # 4. UTCからJSTへ変換
        jst_dt = utc_dt.astimezone(jst_tz)
        return jst_dt

    reserve_price_met = bidding.get('reservePriceMet')
    # reserve_price_metはTrue/False/Noneの可能性があるため、1/0/Noneに変換して保存する
    parsed_reserve_price_met = (1 if reserve_price_met else 0) if reserve_price_met is not None else None
    # データクラスへ格納
    return CatawikiWinningBid(
        item_url=item_url,
        bidding_end_time=_to_dt(dl['BiddingEndTime']),
        bidding_start_time=_to_dt(dl['BiddingStartTime']),
        close_at=_to_dt(auction['closeAt']) if auction.get('closeAt') else None,
        closed_at=_to_dt(auction['closedAt']) if auction.get('closedAt') else None,
        auction_id=dl['auction_id'],
        auction_name=dl['auction_name'],
        auction_theme=dl.get('auction_theme', ""),
        auction_theme_id=dl.get('auction_theme_id', 0),
        auction_type_family_id=dl.get('auction_type_family_id', 0) or 0,
        auction_type_family_name=dl.get('auction_type_family_name', ""),
        auction_type_id=dl.get('auction_type_id', 0),
        category_L0_id=dl.get('category_L0_id', 0),
        category_L0_name=dl.get('category_L0_name', ""),
        category_L1_id=dl.get('category_L1_id', 0),
        category_L1_name=dl.get('category_L1_name', ""),
        category_L2_id=dl.get('category_L2_id', 0),
        category_L2_name=dl.get('category_L2_name', ""),
        lot_id=dl['lot_id'],
        is_closed=1 if lotDetailsData.get('isClosed', False) else 0,
        is_sold=1 if bidding.get('sold', False) else 0,
        current_bid_amount=bidding.get('localizedCurrentBidAmount', 0),
        price_currency=props['userData'].get('currencyCode', 'EUR'),
        reserve_price_met=parsed_reserve_price_met,
        sellerInfo_id=sellerInfo.get('id', 0),
        sellerInfo_url=sellerInfo.get('url', ""),
        sellerInfo_address_country_name=sellerInfo.get('address', {}).get('country', {}).get('name', ''),
    )
