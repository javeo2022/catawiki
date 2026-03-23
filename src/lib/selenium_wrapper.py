# -*- coding: utf-8 -*-
import logging
import time
import os
import sys
import re
import atexit
import psutil
import json
from typing import Optional, Union, Any
from bs4 import BeautifulSoup, element
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from enum import Enum
# from ..config import config

# ==================================================
# 共通待機時間 ※処理の最後にsleepする秒数
COMMON_WAIT_SECONDS = 0.5
# このモジュールのパスと名前 ※PyInstaller対応
if getattr(sys, "frozen", False):
    # PyInstallerでビルドされた実行ファイルの場合
    MODULE_PATH = os.path.dirname(sys.executable)
    MODULE_NAME = os.path.basename(sys.executable).replace(".exe", "")
else:
    # 通常のPythonスクリプト実行の場合
    MODULE_PATH = os.path.dirname(__file__)
    MODULE_NAME = os.path.basename(__file__).replace(".py", "")


# ==================================================
logger = logging.getLogger(__name__)


class SelectBy(Enum):
    Index = "index"
    Value = "value"
    VisibleText = "visible_text"


class SeleniumWrapper:
    def __init__(self, timeout=10, log_level=logging.INFO):
        # ログ設定
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)s: %(message)s", level=log_level
        )
        logger = logging.getLogger(__name__)
        self.timeout = timeout
        logger.info("SeleniumWrapper initialized")
        self.selenium_flg = False
        atexit.register(self.driver_close)  # プログラム終了時にdriver_closeを呼び出す

    def _scroll_to_center(
        self,
        element: WebElement,
        log_output: bool = True,
    ) -> bool:
        """
        memo:
        -----------
        - jsで指定の要素を画面中央にする

        """
        try:
            for _ in range(3):
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                        element,
                    )
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                logger.error(
                    "[ScrollError] Failed to scroll element",
                    exc_info=logger.level <= logging.DEBUG,
                )

            # 最後に画面表示確認する
            self.selenium_wait(
                condition=EC.element_to_be_clickable(element),
                log_output=log_output,
            )
        except Exception as e:
            logger.error(
                f"[ScrollError] Failed to scroll element: {str(e)}",
                exc_info=logger.level <= logging.DEBUG,
            )
            return False
        return True

    def _resolve_timeout(self, timeout: float) -> float:
        """
        memo:
        -----------
        - タイムアウトを引数初期値（-1）ならinitの値にする
        """
        return timeout if timeout != -1 else self.timeout

    def _resolve_element(
        self,
        target: Union[str, WebElement],
        idx: int = 0,
        timeout: float = -1.0,
    ) -> Optional[WebElement]:
        """targetがstrならCSS selectorから取得、WebElementならそのまま返す"""
        timeout = self._resolve_timeout(timeout)
        if isinstance(target, WebElement):
            return target
        elif isinstance(target, str):
            return self._get_element_by_index(target, idx, timeout)
        else:
            logger.error(f"[ResolveError] Invalid target type: {type(target)}")
            return None

    def _safe_click(self, element: WebElement) -> bool:
        """
        memo:
        -----------
        - selenium標準のclickが失敗したらjsでクリックをする2段構えclick
        """
        try:
            WebDriverWait(self.driver, self._resolve_timeout(3)).until(
                EC.element_to_be_clickable(element)
            )
            element.click()
            return True
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as e2:
                logger.error(
                    f"[ClickError] JS click failed: {str(e2)}",
                    exc_info=logger.level <= logging.DEBUG,
                )
                return False

    def _get_element_by_index(
        self, css_selector: str, idx: int = 0, timeout: float = -1
    ) -> Optional[WebElement]:
        """
        Parameters:
        -----------
        css_selector:遷移先のURL
        timeout:WebDriverWaitの最大待機秒数

        memo:
        -----------
        - elementをidx指定で取得するのでEC.presence_of_all_elements_locatedを使う
        - css_selectorがconditionの状態になるまで待機
        """
        timeout = self._resolve_timeout(timeout)
        try:
            elements = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector))
            )
            if len(elements) <= idx:
                logger.warning(f"[NoSuchElement] selector={css_selector}, index={idx}")
                return None
        except TimeoutException:
            logger.warning(f"[Timeout] selector={css_selector}, timeout={timeout}")
            return None
        except Exception as e:
            logger.error(
                f"[Exception] selector={css_selector}, index={idx}, error={str(e)}",
                exc_info=logger.level <= logging.DEBUG,
            )
            return None
        return elements[idx]

    def driver_open(
        self,
        headless: bool = False,
        user_data_dir: Optional[str] = None,  # R"C:\shares\GitHub\netkeiba_scraper\user data",
        imagesEnabled: bool = True,
        download_dir: Optional[str] = None,
        incognito: bool = False,
        enable_js: bool = True,
        enable_performance_log: bool = True,  
    ) -> None:
        """
        chromedriverを起動する

        ↓↓↓参考になりそうなQiita↓↓↓
        https://qiita.com/kawagoe6884/items/cea239681bdcffe31828

        headless:ヘッドレスモードで実行するか
        user_data_dir:ユーザープロファイルを指定する場合フォルダパスを指定※"Default"か"Profile x"を指定
        timeout:デフォルトのタイムアウト値
        imagesEnabled:画像を読み込むかどうか
        download_dir:ダウンロード先フォルダを指定する場合フォルダパスを指定
        incognito:シークレットモードで開くか
        enable_js:JavaScriptを有効にするか
        enable_performance_log:Trueにするとget_status_code()でHTTPステータスコードが取得可能になる
        """
        options = Options()
        ##### 共通オプション
        options.add_argument("--start-maximized")  # 初期のウィンドウ最大化
        options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )  # navigator.webdriver=false となる設定。確認⇒　driver.execute_script("return navigator.webdriver")
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )  # Chromeは自動テスト ソフトウェア~~　を非表示
        prefs = {
            "credentials_enable_service": False,  # パスワード保存のポップアップを無効
            "download_bubble.partial_view_enabled": False,  # ダウンロードが完了したときの通知(吹き出し/下部表示)を無効にする。
            "plugins.always_open_pdf_externally": True,  # Chromeの内部PDFビューアを使わない(＝URLにアクセスすると直接ダウンロードされる)
        }
        ##### 引数で指定するオプション
        # ダウンロード先フォルダが指定されてればフォルダを作ってパラメータを追加する
        if download_dir:
            os.makedirs(download_dir, exist_ok=True)
            # ダウンロード先を指定
            prefs["download.default_directory"] = download_dir
            prefs["savefile.default_directory"] = download_dir
        # ユーザープロファイルフォルダに指定があったら
        if user_data_dir != None:
            options.add_argument(f"--user-data-dir={user_data_dir}")
        # ヘッドレスモードの判定
        if headless is True:
            options.add_argument("--headless=new")
        # 画像を読み込むかの判定
        if imagesEnabled is False:
            options.add_argument("--blink-settings=imagesEnabled=false")
        # シークレットモードの判定
        if incognito is True:
            options.add_argument("--incognito")
        # javascript無効かの判断
        if not enable_js:
            prefs["profile.managed_default_content_settings.javascript"] = 2

        # Performance Logsを有効にする（HTTPステータスコード取得用）
        if enable_performance_log:
            options.set_capability(
                "goog:loggingPrefs", {"performance": "ALL"}
            )

        options.add_experimental_option("prefs", prefs)
        service = Service()
        service.creation_flags = (
            0x08000000  # ヘッドレスモードで DevTools listening on ws:~~ を表示させない
        )
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(10)
        self.driver.implicitly_wait(5)
        time.sleep(3)
        # chromedriverのPID
        chromedriver_pid = self.driver.service.process.pid

        # 子プロセス（Chrome）のPIDを取得
        self.chromedriver_proc = psutil.Process(chromedriver_pid)
        self.chrome_pids = [p.pid for p in self.chromedriver_proc.children()]

        self.driver.maximize_window()
        self.selenium_flg = True
        logger.info("WebDriver started")

    def driver_close(self):
        """
        chromedriverを終わらせる処理
        """
        if self.selenium_flg:
            logger.info("Quitting WebDriver")
            try:
                # self.driver.close()
                self.driver.quit()
            except Exception:
                pass

            try:
                # 念のためchromedriverをkill
                self.chromedriver_proc.kill()
            except Exception:
                pass

            # 念のため残っていたらkill
            for pid in self.chrome_pids:
                try:
                    psutil.Process(pid).kill()
                except psutil.NoSuchProcess:
                    pass

        self.selenium_flg = False

    def get_status_code(self, target_url: Optional[str] = None) -> Optional[int]:
        """
        直前のページ遷移のHTTPステータスコードを返す

        Parameters:
        -----------
        target_url: 確認したいURLを絞り込む場合に指定（Noneなら現在のURLで自動判定）
                    部分一致で検索するので、例えば "example.com/page" のように指定可能

        Returns:
        -----------
        ステータスコード（int）または取得できなかった場合はNone

        memo:
        -----------
        - driver_open(enable_performance_log=True) が必須
        - Performance Logsを使うのでChromeDriver限定
        - get_log("performance") は取得すると同時にバッファがクリアされる仕様のため
          selenium_page_load の直後に呼ぶ必要がある
        """
        url = target_url or self.driver.current_url
        try:
            logs = self.driver.get_log("performance")
        except Exception as e:
            logger.error(
                f"[StatusCodeError] Performance logが取得できませんでした。"
                f"driver_open(enable_performance_log=True) を指定しているか確認してください: {e}"
            )
            return None

        # ログを新しい順に走査して対象URLのレスポンスを探す
        for entry in reversed(logs):
            try:
                message = json.loads(entry["message"])["message"]
                if message.get("method") != "Network.responseReceived":
                    continue
                response = message["params"]["response"]
                if url in response.get("url", ""):
                    status_code = response["status"]
                    logger.info(f"[StatusCode] {status_code} - {response['url']}")
                    return status_code
            except Exception:
                continue

        logger.warning(f"[StatusCodeError] URLに対応するログが見つかりませんでした: {url}")
        return None

    def selenium_wait(
        self,
        condition: Any = EC.presence_of_element_located((By.CSS_SELECTOR, "body")),
        timeout: float = 10.0,
        final_wait_time: float = COMMON_WAIT_SECONDS,
        log_output: bool = True,
    ) -> bool:
        """
        Parameters:
        -----------
        condition:expected_conditions ※指定がなければbodyがあることを確認する
        timeout:WebDriverWaitの最大待機秒数
        final_wait_time:最後にsleepする秒数

        memo:
        -----------
        - getだけじゃなくclickとかの後でも使えるようにwait部分だけの関数にする
        """
        timeout = self._resolve_timeout(timeout=timeout)
        try:
            # JavaScriptを使ってページ全体が読み込まれるまで待機
            wait = WebDriverWait(self.driver, timeout)
            # JavaScriptの読み込み完了を待つ
            wait.until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # ロード完了後に指定のCSSが読み込まれたか確認する ※初期値のbodyはさすがにあるでしょ
            wait.until(condition)
            # 最後に無条件待機を入れる
            time.sleep(final_wait_time)
        except Exception as e:
            # おそらく発生しないException
            if log_output:
                logger.error(
                    f"[WaitError] Failed during wait: {str(e)}",
                    exc_info=logger.level <= logging.DEBUG,
                )
            return False
        return True

    def selenium_page_load(
        self,
        url: str,
        condition: Any = EC.presence_of_element_located((By.CSS_SELECTOR, "body")),
        timeout: float = 10.0,
        max_retries:int = 5,
        final_wait_time: float = COMMON_WAIT_SECONDS,
        log_output: bool = True,
    ) -> bool:
        """
        Parameters:
        -----------
        url:遷移先のURL
        timeout:WebDriverWaitの最大待機秒数
        final_wait_time:最後にsleepする秒数
        load_completion_css:読み込み完了を認知するCSS
        condition:expected_conditions

        memo:
        -----------
        - 結局selenium_waitの前にgetしているだけだけど一番頻度が高いので個別に関数化する
        """
        for attempt in range(max_retries):
            try:
                self.driver.get(url=url)
                self.selenium_wait(
                    condition=condition,
                    timeout=timeout,
                    final_wait_time=final_wait_time,
                    log_output=log_output,
                )
                break
            except (TimeoutException, WebDriverException) as e:
                print(f"エラー発生: {e}")
                if attempt < max_retries:
                    print(f"{COMMON_WAIT_SECONDS}秒待機してからリトライします...\n")
                    time.sleep(COMMON_WAIT_SECONDS)
                else:
                    print("最大リトライ回数に達しました。処理を中断します。")
                    # 最終的にもダメだった場合は例外を発生させる
                    raise e
            except Exception as e:
                raise e
        return True

    def selenium_input(
        self,
        target: Union[str, WebElement],
        idx: int = 0,
        value: str = "",
        timeout: float = -1.0,
        log_output: bool = True,
    ) -> bool:
        """
        Parameters:
        -----------
        target: CSSセレクタ（str）または WebElement
        idx: セレクタで複数要素がある場合のインデックス
        value: 入力する文字列
        timeout: タイムアウト秒数

        memo:
        -----------
        - targetがstrなら要素取得して入力、WebElementならそのまま入力
        """
        timeout = self._resolve_timeout(timeout=timeout)
        # 要素取得
        element: Optional[WebElement] = self._resolve_element(
            target=target, idx=idx, timeout=timeout
        )

        # 要素が見つからなかった場合はFalseを返す
        if element is None:
            return False

        try:
            # 入力可能状態まで待機
            self.selenium_wait(
                condition=EC.element_to_be_clickable(element),
                timeout=timeout,
                log_output=log_output,
            )

            # タグチェック
            if element.tag_name not in ["input", "textarea", "p", "span", "h2", "h3"]:
                logger.error(f"[InputError] Invalid tag for input: {element.tag_name}")
                return False

            # jsで要素を画面中央にスクロール
            self._scroll_to_center(element)
            # 一旦クリアして念のためクリックして入力
            element.clear()
            element.click()
            time.sleep(COMMON_WAIT_SECONDS)
            element.send_keys(value)
            # 入力後にTabキーを送ってフォーカスを外す
            element.send_keys(Keys.TAB)
            time.sleep(COMMON_WAIT_SECONDS)

        except TimeoutException:
            if log_output:
                logger.error(
                    f"[Timeout] Element not clickable for input: timeout={timeout}"
                )
                return False
        except Exception as e:
            if log_output:
                logger.error(
                    f"[Exception] Error in selenium_input: {str(e)}",
                    exc_info=logger.level <= logging.DEBUG,
                )
            return False
        return True

    def selenium_get(
        self,
        target: Union[str, WebElement],
        idx: int = 0,
        att: str = "text_or_value",
        timeout: float = -1.0,
        default_value: str = "",
        log_output: bool = True,
    ) -> str:
        """
        Parameters:
        -----------
        target: CSSセレクタ（str）または WebElement
        idx:インデックスの指定が必要な場合 ※初期値は0
        att:取得する対象 ※textかattributeに指定する値
        timeout:タイムアウトまでの秒数 ※初期値は別途設定
        default_value: elementが見つからなかった時の返値

        memo:
        -----------
        - 文字だけでなく指定要素の値も取得できるようにする
        - hidden要素の取得もあるのでpresence_of_element_locatedを使う
        - 要素がない時は引数で制御して初期値空白を返すようにしている
        """
        timeout = self._resolve_timeout(timeout=timeout)
        # 要素取得
        element: Optional[WebElement] = self._resolve_element(
            target=target, idx=idx, timeout=timeout
        )
        if element is None:
            if log_output:
                logger.error(f"[InputError] Invalid target type: {type(target)}")
            return default_value

        try:
            # 引数の属性に合わせて取得
            ret: str
            if att == "text_or_value":
                # textが空ならvalueを返す
                ret = element.text.strip()
                if not ret:
                    ret = str(element.get_attribute("value")).strip()
            elif att == "text":
                # 明示的にtextが指定された場合はtextしか確認しない
                ret = element.text.strip()
            else:
                # text以外はattの指定にする
                ret = str(element.get_attribute(att)).strip()

        except Exception as e:
            if log_output:
                logger.error(
                    f"[GetError] Failed to get attribute {att}: {str(e)}",
                    exc_info=logger.level <= logging.DEBUG,
                )
            return default_value
        return ret

    def selenium_click(
        self,
        target: Union[str, WebElement],
        idx: int = 0,
        timeout: float = -1.0,
        log_output: bool = True,
    ) -> bool:
        """
        Parameters:
        -----------
        target: CSSセレクタ（str）または WebElement
        idx:インデックスの指定が必要な場合 ※初期値は0
        timeout:タイムアウトまでの秒数 ※初期値は別途設定

        memo:
        -----------
        - クリックするため事前に画面中央に移動してクリックする
        - seleniumのクリックが失敗したらjsでクリックするように内部関数を呼び出す
        """
        timeout = self._resolve_timeout(timeout=timeout)
        # 要素取得
        element: Optional[WebElement] = self._resolve_element(
            target=target, idx=idx, timeout=timeout
        )
        if element is None:
            if log_output:
                logger.error(f"[InputError] Invalid target type: {type(target)}")
            return False

        try:
            # clickしようとしてるから element_to_be_clickable を使う
            self.selenium_wait(
                condition=EC.element_to_be_clickable(element),
                timeout=timeout,
                log_output=log_output,
            )
        except TimeoutException:
            if log_output:
                logger.warning(
                    f"[Timeout] Element not clickable: tag={element.tag_name}, timeout={timeout}"
                )
            return False
        except Exception as e:
            # おそらく発生しないException
            if log_output:
                logger.error(
                    f"[Exception] Unexpected error in selenium_click_elm: {str(e)}",
                    exc_info=logger.level <= logging.DEBUG,
                )
            return False

        # jsで要素を画面中央にスクロール
        self._scroll_to_center(element=element)

        # clickでエラーになったらjsを試してみる
        return self._safe_click(element)

    def selenium_select(
        self,
        target: Union[str, WebElement],
        idx: int = 0,
        select_by: SelectBy = SelectBy.VisibleText,
        value: str = "",
        timeout: float = -1.0,
        log_output: bool = True,
    ) -> bool:
        """
        Parameters:
        -----------
        target: CSSセレクタ（str）または WebElement
        idx:インデックスの指定が必要な場合 ※初期値は0
        select_by: select_byの値
        value: select_byで指定した値
        timeout:タイムアウトまでの秒数 ※初期値は別途設定

        memo:
        -----------
        入力可能状態まで待機するのでelement_to_be_clickableを使う
        """
        timeout = self._resolve_timeout(timeout=timeout)
        # 要素取得
        element: Optional[WebElement] = self._resolve_element(
            target=target, idx=idx, timeout=timeout
        )
        if element is None:
            if log_output:
                logger.error(f"[InputError] Invalid target type: {type(target)}")
            return False

        # selectタグ以外は使わないはず ※select以外で正常タグを見つけたときは修正する
        if element.tag_name != "select":
            if log_output:
                logger.error(
                    f"[SelectError] Invalid tag for select: {element.tag_name}"
                )
            return False

        # jsで要素を画面中央にスクロール
        self._scroll_to_center(element=element)

        # 選択可能状態まで待機
        self.selenium_wait(
            condition=EC.element_to_be_clickable(element),
            log_output=log_output,
        )

        # ここから正常時の操作
        select = Select(element)
        try:
            # 引数のselect_byに合わせて選択
            match select_by:
                case SelectBy.Index:
                    select.select_by_index(int(value))
                case SelectBy.Value:
                    select.select_by_value(str(value))
                case SelectBy.VisibleText:
                    select.select_by_visible_text(str(value))
                case _:
                    if log_output:
                        logger.error(
                            f"[SelectError] Invalid select_by value: {select_by}"
                        )
                    return False

        except ValueError as e:
            if log_output:
                logger.error(
                    f"[SelectError] ValueError during selection by {select_by.name}: {e}"
                )
            return False

        except Exception as e:
            if log_output:
                logger.error(
                    f"[SelectError] Failed to select option by {select_by.name}: {e}",
                    exc_info=logger.level <= logging.DEBUG,
                )
            return False

        time.sleep(COMMON_WAIT_SECONDS)
        return True

    def selenium_find_text_element(
        self,
        target_css_selector: str,
        element_text: str,
        exact_match: bool = True,
    ) -> Optional[WebElement]:
        """
        Parameters:
        -----------
        target: CSSセレクタ
        element_text: 照合したいテキスト
        exact_match: Trueで完全一致、Falseで部分一致（デフォルト）

        memo:
        -----------
        - targetで絞ったelementの中でelement_textに合致する最初のelementを返す
        - 見つからない場合はNoneを返す
        """
        elements = self.driver.find_elements(By.CSS_SELECTOR, target_css_selector)
        for el in elements:
            text = el.get_attribute("textContent") or el.text
            if exact_match:
                if text.strip() == element_text:
                    return el
            else:
                if element_text in text.strip():
                    return el
        return None

    def window_scroll(
        self,
        step: int = 10,
        delay: float = 0.1,
        log_output: bool = True,
    ):
        """
        js対応のためにゆっくり画面を一番下にスクロールする
        """
        try:
            top = 1
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            while top < last_height:
                top = top + step
                self.driver.execute_script(f'window.scrollBy(0, "{str(step)}")')
                last_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                time.sleep(delay)
        except Exception as e:
            if log_output:
                logger.error(
                    f"[ScrollError] Failed during window scroll: {str(e)}",
                    exc_info=logger.level <= logging.DEBUG,
                )

    def reconnect_nordvpn_in_new_tab(self):
        """
        新しいタブを開き、NordVPNの再接続処理を行い、タブを閉じて元のタブに戻る関数
        :param driver: 既に起動している Selenium WebDriver インスタンス
        """
        logger.info("--- VPN再接続処理を開始します ---")
        #  現在のタブのウィンドウハンドルを保存
        original_window = self.driver.current_window_handle
        #  新しいタブを開く
        self.driver.execute_script("window.open('about:blank');")
        #  新しく開いたタブに切り替える
        new_window = [handle for handle in self.driver.window_handles if handle != original_window][0]
        self.driver.switch_to.window(new_window)
        #  NordVPNのUIページに移動
        NORDVPN_UI_URL = 'chrome-extension://fjoaledfpmneenckfbpdfhkmimnjocfa/index.html'
        self.driver.get(NORDVPN_UI_URL)
        try:
            # NordVPNのUIページの読み込み完了を検知
            self.selenium_wait(condition=EC.presence_of_element_located((By.CSS_SELECTOR, "#app")))
            # VPN再接続画面になっていない可能性があるのでサイドメニューをクリックする
            self.selenium_click('div[data-testid="navigation-item-container-vpn"]')
            # 今のIPを控えておく
            old_ip = self.selenium_get('span[data-testid="status-bar-ip"]')
            if self.selenium_get('p[data-testid="status-bar-status"]') == 'Not connected':
                # --- 未接続の場合、接続ボタンをクリックする
                self.selenium_click('button[data-testid="connection-card-quick-connect-button"]')
            else:
                # --- 接続済みの場合、再接続ボタンをクリックする
                self.selenium_click('button[data-testid="connection-card-refresh-button"]')
            time.sleep(1)

            # --- 接続完了を待つ
            for _ in range(10):
                if self.selenium_get('p[data-testid="status-bar-status"]') == 'Connected':
                    break
                else:
                    time.sleep(1)
            else:
                return False

            # 表示されている文字がN/Aの時があるのでIPアドレス型か正規表現でチェックする
            pattern = re.compile(r'^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$')
            for _ in range(10):
                new_ip = self.selenium_get('span[data-testid="status-bar-ip"]')
                if pattern.match(new_ip):
                    break
                else:
                    time.sleep(1)
            else:
                return False
        except Exception as e:
            logger.error(f"再接続処理中にエラーが発生しました: {e}")
        # -------------------------------------------------------------------
        # まれにblankウィンドウが残るので余計なウィンドウを順番に閉じる
        while True:
            for handle in self.driver.window_handles:
                if handle != original_window:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                    break
            else:
                break
        # 6. 元のタブに戻す
        self.driver.switch_to.window(original_window)
        # 処理が元のタブに戻ったことを確認するための動作（任意）
        # self.driver.refresh()
        logger.info(f'{old_ip} → {new_ip} へ再接続しました')


def get_element_attribute_or_text(soup_object: element.Tag, selector: str, index: int = 0, separator: str = "", attribute: str | None = None, default: str = "") -> str:
    """
    指定されたセレクタで要素を取得し、属性値またはテキストを返す。
    要素が見つからない場合はNoneを返す。
    属性が指定された場合はその属性値を、指定されない場合は要素のテキストを返す。

    Args:
        soup_object: BeautifulSoupのオブジェクト
        selector: CSSセレクタ文字列
        attribute: 取得したい属性名 (str)。Noneの場合はテキストを返す
        default: soup_objectがNoneだった時に返す値

    Returns:
        要素の属性値 (str) またはテキスト (str)
    """
    element = soup_object.select(selector)
    if element:
        if attribute:
            return element[index].get(attribute)
        else:
            return element[index].get_text(separator=separator, strip=True)
    else:
        return default