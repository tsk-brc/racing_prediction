# coding:utf-8
"""
対象のサイトからHTMLファイルを直接取得する
URL形式: https://kyoteibiyori.com/race_shusso.php?place_no={place_no}&race_no={race_no}&hiduke={yyyymmdd}&slider={0-3}
"""
import argparse
import configparser
import datetime
import logging
import os
import re
import time
from os import path

import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup

config = configparser.ConfigParser()
config.read(os.getcwd() + "/config.ini", encoding="utf-8")

now_datetime = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))

OWN_FILE_NAME = path.splitext(path.basename(__file__))[0]
# 取得したhtmlを格納するフォルダ
KYOTEI_HTML_DIR = os.getcwd() + config.get("DIR", "KYOTEI_HTML_DIR")
# ベースURL
KYOTEI_BASE_URL = config.get("URL", "KYOTEI_BASE_URL")
# ログファイル名
logger = logging.getLogger(__name__)
# HTMLを作成する開始年
FROM_YEAR = config.getint("CONST", "FROM_YEAR")

# place_noの範囲
PLACE_NO_MIN = 1
PLACE_NO_MAX = 24

# race_noの範囲
RACE_NO_MIN = 1
RACE_NO_MAX = 12

# sliderの値（0, 1, 2, 3）
# sliderはページ内のタブ切り替え用のため、slider=0のみを取得する
SLIDER_VALUES = [0]

# IP制限対策: 待機時間の設定（秒）
BASE_WAIT_TIME = 10  # 基本的な待機時間
TAB_WAIT_TIME = 10  # タブ間の待機時間
ERROR_WAIT_TIME = 60  # エラー発生時の待機時間（1分）
IP_BLOCK_WAIT_TIME = 600  # IP制限と判断した場合の待機時間（10分）
MAX_CONSECUTIVE_ERRORS = 3  # 連続エラー許容回数


def init_webdriver():
    """
    Selenium WebDriverを初期化する

    Returns:
        webdriver.Firefox: 初期化されたWebDriverインスタンス
    """
    # Firefox Optionsの設定
    options = Options()
    # ヘッドレスモードを有効にする
    options.add_argument('-headless')
    # ログレベルを設定
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference('useAutomationExtension', False)
    # ページ読み込みタイムアウトを延長
    options.set_preference("dom.max_script_run_time", 0)
    options.set_preference("dom.max_chrome_script_run_time", 0)

    # Firefoxのバイナリパスを設定（macOSの場合）
    firefox_binary_paths = [
        '/Applications/Firefox.app/Contents/MacOS/firefox',
        '/usr/bin/firefox',
        '/usr/local/bin/firefox',
    ]
    for firefox_path in firefox_binary_paths:
        if os.path.exists(firefox_path):
            options.binary_location = firefox_path
            break

    # geckodriverサービスの設定
    service = Service(log_output=os.path.join(os.getcwd(), 'geckodriver.log'))

    try:
        # WebDriverを起動する
        driver = webdriver.Firefox(options=options, service=service)
        # ドライバが設定されるまでの待機時間(秒)
        driver.implicitly_wait(10)
        # ページ読み込みタイムアウトを延長（600秒 = 10分）
        driver.set_page_load_timeout(600)
        # スクリプト実行タイムアウトを延長（600秒 = 10分）
        driver.set_script_timeout(600)
        return driver
    except Exception as e:
        logger.error(f"Firefox WebDriverの起動に失敗しました: {str(e)}")
        logger.error(f"geckodriver.logを確認してください: {os.path.join(os.getcwd(), 'geckodriver.log')}")
        raise


def get_kyotei_html_by_date_with_selenium(driver, year, month, day, place_no, race_no, slider, start_from_tab=None):
    """
    Seleniumを使用して指定した日付、place_no、race_no、sliderのHTMLを取得する

    Args:
        driver: WebDriverインスタンス
        year: 年
        month: 月
        day: 日
        place_no: 競艇場ID (1-24)
        race_no: レース番号 (1-12)
        slider: スライダー値 (0-3)
        start_from_tab: 開始するタブ名（例: "枠別情報"）。Noneの場合はすべてのタブを処理

    Returns:
        bool or None: 成功した場合True、データなしの場合None、エラーの場合False
    """
    # 日付をyyyymmdd形式に変換
    date_str = f"{year}{month:02d}{day:02d}"

    # URLを生成
    url = (
        f"{KYOTEI_BASE_URL}?"
        f"place_no={place_no}"
        f"&race_no={race_no}"
        f"&hiduke={date_str}"
        f"&slider={slider}"
    )

    # HTMLを保存するフォルダ(/html_kyotei/yyyy/mm 配下に保存)
    save_dir = KYOTEI_HTML_DIR + f"{year}/{month:02d}"
    # フォルダが存在しなければ新規作成
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)

    # 保存するファイル名
    file_name = f"{date_str}_{place_no}_{race_no}_{slider}.html"
    save_file_path = save_dir + "/" + file_name

    # 対象のファイルが既に存在する場合はスキップ
    if os.path.isfile(save_file_path):
        logger.debug(f"既に取得済み: {save_file_path}")
        return True

    try:
        # 最初のページを開く（リトライロジック付き）
        initial_load_success = False
        max_initial_retries = 3
        initial_retry_count = 0
        while initial_retry_count < max_initial_retries and not initial_load_success:
            try:
                # ページを開く
                driver.set_page_load_timeout(600)
                driver.get(url)

                # エラーページ（about:neterror）に到達していないかチェック
                current_url = driver.current_url
                if "about:neterror" in current_url or "about:error" in current_url:
                    # netTimeoutエラーの場合はIP制限の可能性が高い
                    is_net_timeout = "nettimeout" in current_url.lower()
                    wait_time = IP_BLOCK_WAIT_TIME if is_net_timeout else ERROR_WAIT_TIME * (initial_retry_count + 1)
                    
                    logger.warning(f"エラーページに到達しました (リトライ {initial_retry_count + 1}/{max_initial_retries}): {current_url}")
                    if is_net_timeout:
                        logger.warning(f"IP制限の可能性があります。{wait_time}秒待機します...")
                    else:
                        logger.warning(f"{wait_time}秒待機してからリトライします...")
                    
                    if initial_retry_count < max_initial_retries - 1:
                        initial_retry_count += 1
                        # エラーページから抜け出すため、about:blankに遷移
                        try:
                            driver.get("about:blank")
                            time.sleep(1)
                        except:
                            pass
                        # IP制限対策: 長時間待機
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"エラーページから復帰できませんでした: {url}")
                        logger.error(f"IP制限の可能性が高いため、{IP_BLOCK_WAIT_TIME}秒待機してから処理を終了します")
                        time.sleep(IP_BLOCK_WAIT_TIME)
                        return False

                initial_load_success = True
            except Exception as e:
                error_str = str(e).lower()
                error_message = str(e)

                # エラーページに到達しているかチェック（例外発生後も確認）
                is_error_page = False
                try:
                    current_url = driver.current_url
                    if "about:neterror" in current_url or "about:error" in current_url:
                        is_error_page = True
                        logger.warning(f"エラーページに到達しています (例外発生後): {current_url}")
                except:
                    pass

                # netTimeoutエラーやタイムアウトエラーを検出
                if is_error_page or "timeout" in error_str or "timed out" in error_str or "nettimeout" in error_str or "reached error page" in error_str:
                    # netTimeoutエラーの場合はIP制限の可能性が高い
                    is_net_timeout = "nettimeout" in error_str
                    wait_time = IP_BLOCK_WAIT_TIME if is_net_timeout else ERROR_WAIT_TIME * (initial_retry_count + 1)
                    
                    logger.warning(f"ページ読み込みタイムアウト/エラーページ到達 (リトライ {initial_retry_count + 1}/{max_initial_retries}): {error_message}")
                    if is_net_timeout:
                        logger.warning(f"IP制限の可能性があります。{wait_time}秒待機します...")
                    else:
                        logger.warning(f"{wait_time}秒待機してからリトライします...")
                    
                    if initial_retry_count < max_initial_retries - 1:
                        initial_retry_count += 1
                        # エラーページから抜け出すため、about:blankに遷移
                        try:
                            driver.get("about:blank")
                            time.sleep(1)
                        except:
                            pass
                        # IP制限対策: 長時間待機
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"ページ読み込みがタイムアウトしました（最大リトライ回数に達しました）: {url}")
                        logger.error(f"IP制限の可能性が高いため、{IP_BLOCK_WAIT_TIME}秒待機してから処理を終了します")
                        time.sleep(IP_BLOCK_WAIT_TIME)
                        return False
                else:
                    # その他のエラーは再発生させる
                    logger.error(f"ページ読み込みで予期しないエラー: {error_message}")
                    raise

        if not initial_load_success:
            logger.error(f"ページの初期読み込みに失敗しました: {url}")
            return False

        # ページが完全に読み込まれるまで待機
        wait = WebDriverWait(driver, 30)

        # ページの基本構造が読み込まれるまで待機
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except Exception:
            pass

        # 「データはありません。」が表示されているかチェック
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if "データはありません。" in page_text:
                logger.warning(f"データなしのためスキップ: {url}")
                return None  # データなしは正常なスキップなのでNoneを返す
        except Exception as e:
            logger.debug(f"データチェックでエラー: {str(e)}")
            pass

        # 基本的なページ読み込み完了を待機（「データ取得中です」は待たない）
        time.sleep(BASE_WAIT_TIME)

        # 各タブごとにHTMLを保存する
        # slider=0で開いた場合、各sliderパラメータでページを開いてHTMLを保存
        if slider == 0:
            # sliderパラメータとタブ名のマッピング
            slider_tab_mapping = {
                0: "基本情報",
                1: "枠別情報",
                2: "モータ情報",
                3: "今節成績",
                7: "結果",
            }

            saved_count = 0

            # 特定のタブから開始する場合の処理
            start_processing = start_from_tab is None

            for slider_value, tab_name in slider_tab_mapping.items():
                # 特定のタブから開始する場合、そのタブに到達するまでスキップ
                if start_from_tab and not start_processing:
                    if tab_name == start_from_tab:
                        start_processing = True
                    else:
                        logger.info(f"タブ '{tab_name}' をスキップします（{start_from_tab}から開始）")
                        continue

                retry_count = 0
                max_retries = 3
                success = False

                while retry_count < max_retries and not success:
                    try:
                        # 各sliderパラメータでURLを開く
                        tab_url = (
                            f"{KYOTEI_BASE_URL}?"
                            f"place_no={place_no}"
                            f"&race_no={race_no}"
                            f"&hiduke={date_str}"
                            f"&slider={slider_value}"
                        )

                        # ページを開く（タイムアウトエラーの可能性があるため、try-exceptで囲む）
                        try:
                            # ページ読み込みタイムアウトを一時的に延長してページを開く（600秒 = 10分）
                            driver.set_page_load_timeout(600)
                            driver.get(tab_url)
                        except Exception as e:
                            error_str = str(e).lower()
                            if "timeout" in error_str or "timed out" in error_str or "nettimeout" in error_str:
                                # netTimeoutエラーの場合はIP制限の可能性が高い
                                is_net_timeout = "nettimeout" in error_str
                                wait_time = IP_BLOCK_WAIT_TIME if is_net_timeout else ERROR_WAIT_TIME * (retry_count + 1)
                                
                                logger.warning(f"ページ読み込みタイムアウト (slider={slider_value}, タブ={tab_name}): {str(e)}")
                                if is_net_timeout:
                                    logger.warning(f"IP制限の可能性があります。{wait_time}秒待機します...")
                                
                                # タイムアウトした場合は、リトライする
                                if retry_count < max_retries - 1:
                                    retry_count += 1
                                    logger.info(f"リトライします (slider={slider_value}, タブ={tab_name}, {retry_count}/{max_retries})")
                                    time.sleep(wait_time)
                                    continue
                                else:
                                    logger.warning(f"ページ読み込みがタイムアウトしました。部分的なHTMLを取得します。")
                                    # タイムアウトしても続行（部分的なHTMLでも取得を試みる）
                                    # ページの読み込みを停止
                                    try:
                                        driver.execute_script("window.stop();")
                                    except:
                                        pass
                                    # タイムアウトしても続行
                                    success = True
                            else:
                                raise

                        # ページの基本構造が読み込まれるまで待機（短縮）
                        try:
                            wait = WebDriverWait(driver, 10)
                            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        except Exception:
                            pass

                        # 基本的な読み込み待機（短縮）
                        time.sleep(0.5)
                        if not success:
                            success = True

                    except Exception as e:
                        error_str = str(e).lower()
                        if "timeout" in error_str or "timed out" in error_str or "nettimeout" in error_str:
                            # netTimeoutエラーの場合はIP制限の可能性が高い
                            is_net_timeout = "nettimeout" in error_str
                            wait_time = IP_BLOCK_WAIT_TIME if is_net_timeout else ERROR_WAIT_TIME * (retry_count + 1)
                            
                            if is_net_timeout:
                                logger.warning(f"IP制限の可能性があります。{wait_time}秒待機します...")
                            
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                logger.warning(f"ページ読み込みをリトライします (slider={slider_value}, タブ={tab_name}, {retry_count}/{max_retries}): {str(e)}")
                                time.sleep(wait_time)
                                continue
                            else:
                                logger.warning(f"ページ読み込みがタイムアウトしました。部分的なHTMLを取得します。")
                                # タイムアウトしても続行
                                try:
                                    driver.execute_script("window.stop();")
                                except:
                                    pass
                                success = True
                        else:
                            retry_count += 1
                            if retry_count >= max_retries:
                                logger.error(f"ページ読み込みに失敗しました (slider={slider_value}, タブ={tab_name}, リトライ{retry_count}回目): {str(e)}")
                                break
                            logger.warning(f"ページ読み込みをリトライします (slider={slider_value}, タブ={tab_name}, {retry_count}/{max_retries}): {str(e)}")
                            time.sleep(ERROR_WAIT_TIME * retry_count)
                            continue

                if not success:
                    logger.warning(f"ページ読み込みに失敗しました。スキップします。 (slider={slider_value}, タブ={tab_name})")
                    continue

                try:
                    # 各タブごとに必要な情報が表示されるまで待機
                    # 各タブで必要なキーワードのマッピング
                    tab_keywords = {
                        0: None,  # 基本情報: 特別な待機なし
                        1: "出遅率",  # 枠別情報
                        2: "貢献P",  # モータ情報
                        3: "順位P",  # 今節成績
                        7: "3連単",  # 結果
                    }

                    keyword = tab_keywords.get(slider_value)
                    if keyword:
                        # 必要なキーワードが表示されるまで待機（最大10秒）
                        max_keyword_wait = 10
                        keyword_wait_start = time.time()
                        while time.time() - keyword_wait_start < max_keyword_wait:
                            try:
                                page_text = driver.find_element(By.TAG_NAME, "body").text
                                if keyword in page_text:
                                    break
                                time.sleep(0.3)
                            except Exception:
                                break

                        # 追加の待機時間（データ読み込みを確実にするため）
                        time.sleep(0.5)

                    # このタブのHTMLを保存
                    tab_file_name = f"{date_str}_{place_no}_{race_no}_{tab_name}.html"
                    tab_save_file_path = save_dir + "/" + tab_file_name

                    # 既に存在する場合はスキップ
                    if os.path.isfile(tab_save_file_path):
                        logger.debug(f"既に取得済み: {tab_save_file_path}")
                        saved_count += 1
                        continue

                    # HTMLを取得（タイムアウトエラーに対応）
                    html = None
                    try:
                        html = driver.page_source
                    except Exception as e:
                        error_str = str(e).lower()
                        if "timeout" in error_str or "timed out" in error_str:
                            logger.warning(f"HTML取得時にタイムアウト (slider={slider_value}, タブ={tab_name}): {str(e)}")
                            # タイムアウトした場合は、JavaScriptでHTMLを取得
                            try:
                                html = driver.execute_script("return document.documentElement.outerHTML;")
                                logger.info(f"JavaScriptでHTMLを取得しました (slider={slider_value}, タブ={tab_name})")
                            except Exception as js_e:
                                logger.error(f"JavaScriptでのHTML取得も失敗 (slider={slider_value}, タブ={tab_name}): {str(js_e)}")
                                continue
                        else:
                            logger.error(f"HTML取得でエラー (slider={slider_value}, タブ={tab_name}): {str(e)}")
                            continue

                    if not html:
                        logger.warning(f"HTMLが取得できませんでした (slider={slider_value}, タブ={tab_name})")
                        continue

                    # 「データはありません。」が実際に表示されるコンテンツ部分に含まれているかチェック
                    soup = BeautifulSoup(html, 'html.parser')
                    # scriptタグとstyleタグを削除
                    for script in soup(["script", "style"]):
                        script.decompose()
                    # 実際に表示されるテキストを取得
                    visible_text = soup.get_text()

                    # 「データはありません。」が実際に表示されるテキストに含まれている場合、スキップ
                    if "データはありません。" in visible_text:
                        logger.warning(f"データなしのためスキップ: {tab_url} ({tab_name})")
                        # データなしの場合は、このタブの処理をスキップして次のタブへ
                        continue

                    # HTMLを保存
                    with open(tab_save_file_path, "w", encoding="utf-8") as file:
                        file.write(html)
                    saved_count += 1

                    # タブ間の待機時間（IP制限対策）
                    time.sleep(TAB_WAIT_TIME)

                except Exception as e:
                    logger.error(f"タブ '{tab_name}' (slider={slider_value}) の処理中にエラーが発生しました: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue

            # すべてのタブの処理が完了
            if saved_count > 0:
                return True
            else:
                logger.warning(f"HTMLを取得できませんでした: {url} (全{len(slider_tab_mapping)}タブで処理失敗)")
                return False
        else:
            # slider=0以外の場合は、従来通り1つのHTMLを保存
            # HTMLを取得する前に、再度「データ取得中です。」が消えていることを確認
            max_retries = 5
            retry_count = 0
            while retry_count < max_retries:
                try:
                    modal_common = driver.find_element(By.ID, "modal_common")
                    if modal_common.is_displayed() and "データ取得中です" in modal_common.text:
                        logger.debug(f"データ読み込み中... ({retry_count + 1}/{max_retries})")
                        time.sleep(2)
                        retry_count += 1
                        continue
                    else:
                        break
                except Exception:
                    # modal_commonが見つからない場合は読み込み完了とみなす
                    break

            if retry_count >= max_retries:
                logger.warning(f"データ読み込みがタイムアウトしました: {url}")

            # 最終的な待機時間
            time.sleep(2)

            # HTMLを取得
            html = driver.page_source

            # HTMLが空でないことを確認
            if len(html) > 0:
                # 「データはありません。」が実際に表示されるコンテンツ部分に含まれているかチェック
                soup = BeautifulSoup(html, 'html.parser')
                # scriptタグとstyleタグを削除
                for script in soup(["script", "style"]):
                    script.decompose()
                # 実際に表示されるテキストを取得
                visible_text = soup.get_text()

                # 「データはありません。」が実際に表示されるテキストに含まれている場合、スキップ
                if "データはありません。" in visible_text:
                    logger.debug(f"データなしのためスキップ: {url}")
                    return None  # データなしは正常なスキップなのでNoneを返す

                # HTMLを保存
                with open(save_file_path, "w", encoding="utf-8") as file:
                    file.write(html)
                logger.info(f"HTML取得成功: {url} -> {save_file_path}")

                # 待機時間（IP制限対策）
                time.sleep(BASE_WAIT_TIME)
                return True
            else:
                logger.warning(f"HTMLが空です: {url}")
                return False

    except Exception as e:
        logger.error(f"エラー発生 ({url}): {str(e)}")
        return False


def get_kyotei_html_by_date(driver, year, month, day, place_no, race_no, slider):
    """
    指定した日付、place_no、race_no、sliderのHTMLを取得する（Selenium使用）

    Args:
        driver: WebDriverインスタンス
        year: 年
        month: 月
        day: 日
        place_no: 競艇場ID (1-24)
        race_no: レース番号 (1-12)
        slider: スライダー値 (0-3)

    Returns:
        bool: 成功した場合True、失敗した場合False
    """
    return get_kyotei_html_by_date_with_selenium(driver, year, month, day, place_no, race_no, slider)


def get_kyotei_html_by_date_and_place_no(driver, year, month, day, place_no):
    """
    指定した日付とplace_noの全レースのHTMLを取得する

    Args:
        driver: WebDriverインスタンス
        year: 年
        month: 月
        day: 日
        place_no: 競艇場ID (1-24)
    """
    success_count = 0
    consecutive_errors = 0
    
    for race_no in range(RACE_NO_MIN, RACE_NO_MAX + 1):
        for slider in SLIDER_VALUES:
            try:
                result = get_kyotei_html_by_date(driver, year, month, day, place_no, race_no, slider)
                if result is True:
                    # 成功した場合
                    success_count += 1
                    consecutive_errors = 0  # 成功したらエラーカウントをリセット
                elif result is None:
                    # データなしの場合（正常なスキップ）はエラーカウントに含めない
                    consecutive_errors = 0  # データなしは正常なのでエラーカウントをリセット
                else:
                    # エラーの場合（False）
                    consecutive_errors += 1
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"レース取得エラー (place_no={place_no}, race_no={race_no}): {str(e)}")
            
            # 連続エラーが発生した場合、長時間待機（データなしの場合は待機しない）
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                logger.warning(f"連続{consecutive_errors}回エラーが発生しました。IP制限の可能性があるため、{IP_BLOCK_WAIT_TIME}秒待機します...")
                time.sleep(IP_BLOCK_WAIT_TIME)
                consecutive_errors = 0  # 待機後にリセット
            
            # レース間の待機時間（IP制限対策）
            time.sleep(BASE_WAIT_TIME)


def get_kyotei_html_by_date_all_place_nos(driver, year, month, day):
    """
    指定した日付の全place_noの全レースのHTMLを取得する

    Args:
        driver: WebDriverインスタンス
        year: 年
        month: 月
        day: 日
    """
    logger.info(f"{year}年{month:02d}月{day:02d}日の全place_noのHTMLを取得します")

    # 日付単位で実行するときに1つのWebDriverを使い続けると、
    # 実行時間が長くなった終盤でタイムアウトが発生しやすくなる。
    # そのため、場ごと（place_noごと）にWebDriverを再起動して負荷を分散する。
    for place_no in range(PLACE_NO_MIN, PLACE_NO_MAX + 1):
        logger.info(f"{year}年{month:02d}月{day:02d}日 place_no={place_no} のHTMLを取得します（WebDriverを場ごとに再起動）")
        local_driver = None
        try:
            # 場ごとに新しいWebDriverを起動
            local_driver = init_webdriver()
            get_kyotei_html_by_date_and_place_no(local_driver, year, month, day, place_no)
        except Exception as e:
            logger.error(f"{year}年{month:02d}月{day:02d}日 place_no={place_no} の処理中にエラーが発生しました: {str(e)}")
        finally:
            # 場ごとにWebDriverを確実に終了
            if local_driver:
                try:
                    local_driver.close()
                    local_driver.quit()
                except Exception:
                    pass
        
        # place_no間の待機時間（IP制限対策）
        if place_no < PLACE_NO_MAX:
            time.sleep(BASE_WAIT_TIME * 2)  # place_no間は少し長めに待機


def get_kyotei_html_by_year_and_month(driver, year, month):
    """
    指定した年月の全レースのHTMLを取得する

    Args:
        driver: WebDriverインスタンス
        year: 年
        month: 月
    """
    logger.info(f"{year}年{month:02d}月のHTMLを取得します")

    # 月の日数を取得
    if month == 12:
        days_in_month = 31
    else:
        next_month = datetime.date(year, month + 1, 1)
        days_in_month = (next_month - datetime.timedelta(days=1)).day

    for day in range(1, days_in_month + 1):
        # 日付の妥当性を確認
        try:
            date_obj = datetime.date(year, month, day)
            # 過去の日付のみ処理（今日以降はスキップ）
            if date_obj <= now_datetime.date():
                get_kyotei_html_by_date_all_place_nos(driver, year, month, day)
        except ValueError:
            # 無効な日付（例: 2月30日）はスキップ
            continue


def get_kyotei_html(driver):
    """
    全期間のHTMLを取得する

    Args:
        driver: WebDriverインスタンス
    """
    # 昨年までのデータを取得
    for year in range(FROM_YEAR, now_datetime.year):
        for month in range(1, 13):
            get_kyotei_html_by_year_and_month(driver, year, month)

    # 今年のデータを取得
    for year in range(now_datetime.year, now_datetime.year + 1):
        for month in range(1, now_datetime.month + 1):
            get_kyotei_html_by_year_and_month(driver, year, month)


def clean_slider_duplicates(year=None, month=None):
    """
    slider=1,2,3の重複ファイルを削除する（slider=0のみ残す）

    Args:
        year: 年（指定しない場合は全期間）
        month: 月（指定しない場合は全年）
    """
    logger.info("slider=1,2,3の重複ファイル削除処理を開始します")
    deleted_count = 0

    if year and month:
        # 指定年月のみ処理
        years = [year]
        months = [month]
    elif year:
        # 指定年の全月を処理
        years = [year]
        months = range(1, 13)
    else:
        # 全期間を処理
        years = range(FROM_YEAR, now_datetime.year + 1)
        months = range(1, 13)

    for year in years:
        for month in months:
            html_dir = KYOTEI_HTML_DIR + f"{year}/{month:02d}"
            if not os.path.isdir(html_dir):
                continue

            # ファイル一覧を取得
            file_list = os.listdir(html_dir)
            logger.info(f"{year}年{month:02d}月: {len(file_list)}件のファイルをチェックします")

            for file_name in file_list:
                if not file_name.endswith('.html'):
                    continue

                # ファイル名の形式: {place_no}_{race_no}_{yyyymmdd}_{slider}.html
                parts = file_name.replace('.html', '').split('_')
                if len(parts) == 4:
                    slider_value = parts[3]
                    # slider=1,2,3のファイルを削除
                    if slider_value in ['1', '2', '3']:
                        file_path = os.path.join(html_dir, file_name)
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.debug(f"削除: {file_path}")
                        except Exception as e:
                            logger.error(f"ファイル削除エラー ({file_path}): {str(e)}")

    logger.info(f"slider=1,2,3の重複ファイル削除処理を完了しました（{deleted_count}件削除）")


if __name__ == "__main__":
    # コマンドライン引数のパーサーを設定
    parser = argparse.ArgumentParser(description="ボートレースのHTMLを取得します")
    parser.add_argument("--year", type=int, help="年を指定します（例: 2025）")
    parser.add_argument("--month", type=int, help="月を指定します（例: 11）")
    parser.add_argument("--day", type=int, help="日を指定します（例: 30）")
    parser.add_argument("--place-no", type=int, help="競艇場IDを指定します（1-24）")
    parser.add_argument("--race-no", type=int, help="レース番号を指定します（1-12）")
    parser.add_argument("--slider", type=int, help="スライダー値を指定します（0-3）")
    parser.add_argument("--clean-slider", action="store_true", help="slider=1,2,3の重複ファイルを削除します（slider=0のみ残します）")
    args = parser.parse_args()

    # ログフォーマットを定義
    formatter = "%(asctime)s [%(levelname)s]\t%(message)s"
    # ログファイルを定義
    logging.basicConfig(
        filename="log/activity.log", level=logging.INFO, format=formatter
    )

    # 処理開始をログに出力
    logger.info("ボートレース HTML取得処理を開始します")

    # --clean-sliderオプションが指定された場合は削除処理のみ実行
    if args.clean_slider:
        clean_slider_duplicates(args.year, args.month)
        logger.info("ボートレース HTML削除処理を終了します")
    else:
        # WebDriverを初期化
        driver = None
        try:
            driver = init_webdriver()

            # コマンドライン引数に応じて処理を分岐
            if args.year and args.month and args.day and args.place_no and args.race_no and args.slider is not None:
                # 特定の日付、place_no、race_no、sliderを取得
                get_kyotei_html_by_date(driver, args.year, args.month, args.day, args.place_no, args.race_no, args.slider)
            elif args.year and args.month and args.day and args.place_no:
                # 特定の日付、place_noの全レースを取得
                get_kyotei_html_by_date_and_place_no(driver, args.year, args.month, args.day, args.place_no)
            elif args.year and args.month and args.day:
                # 特定の日付の全place_noの全レースを取得
                get_kyotei_html_by_date_all_place_nos(driver, args.year, args.month, args.day)
            elif args.year and args.month:
                # 特定の年月の全レースを取得
                get_kyotei_html_by_year_and_month(driver, args.year, args.month)
            else:
                # 引数が指定されていない場合は全期間のデータを取得
                get_kyotei_html(driver)

        except Exception as e:
            logger.error(f"HTML取得処理中にエラーが発生しました: {str(e)}")
            raise
        finally:
            # WebDriverを終了
            if driver:
                try:
                    driver.close()
                    driver.quit()
                except:
                    pass

    # 処理終了をログに出力
    logger.info("ボートレース HTML取得処理を終了します")

