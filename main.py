import sys
from src.scraper.scraping_module import CatawikiScraper
from src.utils.logger import get_logger
import logging


def main():
    get_logger()
    scraper = CatawikiScraper()
    winning_bid_only = True if len(sys.argv) > 1 and sys.argv[1] == "--winning-bid" else False
    try:
        if not winning_bid_only:
            scraper.scraping_list()
        scraper.scraping_winning_bid()
    except Exception as e:
        logging.error(f'エラーが発生しました: {e}')
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
