# coding:utf-8

"""
指定した期間のURLを入手する
https://db.netkeiba.com/
にあるJRAのレースのURLを取得する
"""
from selenium.webdriver.support.ui import Select, WebDriverWait
import chromedriver_binary
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
import logging
from os import path
import os
import re
import pytz
import time
import datetime
import configparser


config = configparser.ConfigParser()
config.read(os.getcwd() + '/config.ini', encoding='utf-8')

now_datetime = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))

OWN_FILE_NAME = path.splitext(path.basename(__file__))[0]
# ログファイル名
logger = logging.getLogger(__name__)
# URL情報を格納するフォルダ
RACE_URL_DIR = os.getcwd() + config.get('DIR', 'RACE_URL_DIR')
# URLを取得するサイト
URL = config.get('URL', 'KEIBA_DB_URL')
# URLを取得する開始年
FROM_YEAR = config.getint('CONST', 'FROM_YEAR')


def get_race_url():
    # FireFox Optionsの設定
    options = Options()
    # ヘッドレスモードを有効にする
    options.headless = True
    # Firefoxのバイナリパスを指定する
    options.binary_location = '/Applications/Firefox.app/Contents/MacOS/firefox'
    # WebDriverを起動する
    driver = webdriver.Firefox(firefox_options=options)
    # ドライバが設定されるまでの待機時間(秒)
    driver.implicitly_wait(10)
    # 昨年までのデータを取得
    for year in range(FROM_YEAR, now_datetime.year):
        for month in range(1, 13):
            # URL一覧を記載するファイル名(yyyymm.txt)
            race_url_file = RACE_URL_DIR + \
                str(year) + str('{0:02d}'.format(month)) + ".txt"
            # ファイルが存在しなければ取得
            if not os.path.isfile(race_url_file):
                logger.info(
                    str(year) + "年" + str('{0:02d}'.format(month)) + "月のURL情報を取得します")
                get_race_url_by_year_and_month(driver, year, month)
    # 今年の開始から先月までのデータを取得
    for year in range(now_datetime.year, now_datetime.year + 1):
        for month in range(1, now_datetime.month):
            # URL一覧を記載するファイル名(yyyymm.txt)
            race_url_file = RACE_URL_DIR + \
                str(year) + str('{0:02d}'.format(month)) + ".txt"
            # ファイルが存在しなければ取得
            if not os.path.isfile(race_url_file):
                logger.info(
                    str(year) + "年" + str('{0:02d}'.format(month)) + "月のURL情報を取得します")
                get_race_url_by_year_and_month(driver, year, month)
    # 今月のデータを取得
    logger.info(str(now_datetime.year) +
                "年" + str('{0:02d}'.format(now_datetime.month)) + "月のURL情報を取得します")
    get_race_url_by_year_and_month(
        driver, now_datetime.year, now_datetime.month)

    # Chrome Driverを終了する
    driver.close()
    driver.quit()


def get_race_url_by_year_and_month(driver, year, month):
    # URL一覧を記載するファイル名(yyyymm.txt)
    race_url_file = RACE_URL_DIR + \
        str(year) + str('{0:02d}'.format(month)) + ".txt"

    # Webページを開く
    driver.get(URL)
    # 1秒待機
    time.sleep(1)
    # ページ上のすべての要素が読み込まれるまで10秒待機
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_all_elements_located)

    # 期間を選択
    start_year_element = driver.find_element_by_name('start_year')
    start_year_select = Select(start_year_element)
    start_year_select.select_by_value(str(year))
    start_mon_element = driver.find_element_by_name('start_mon')
    start_mon_select = Select(start_mon_element)
    start_mon_select.select_by_value(str(month))
    end_year_element = driver.find_element_by_name('end_year')
    end_year_select = Select(end_year_element)
    end_year_select.select_by_value(str(year))
    end_mon_element = driver.find_element_by_name('end_mon')
    end_mon_select = Select(end_mon_element)
    end_mon_select.select_by_value(str(month))

    # JRAの競馬場を全てチェック
    for i in range(1, 11):
        terms = driver.find_element_by_id('check_Jyo_' + str(i).zfill(2))
        terms.click()

    # 表示件数「100」を選択
    # list_element = driver.find_element_by_name(
    #    "list").location_once_scrolled_into_view
    #list_number = Select(list_element)
    # list_number.select_by_value('100')

    # フォームを送信
    form = driver.find_element_by_css_selector("#db_search_detail_form > form")
    form.submit()
    # 5秒待機
    time.sleep(5)
    # ページ上のすべての要素が読み込まれるまで10秒待機
    wait.until(EC.presence_of_all_elements_located)
    # 件数に該当するフォームの要素を取得
    total_num_and_now_num = driver.find_element_by_xpath(
        "//*[@id='contents_liquid']/div[1]/div[2]").text
    # 件数を取得
    total_num = int(
        re.search(r'(.*)件中', total_num_and_now_num).group().strip("件中"))
    # 既に取得済みの件数
    pre_url_num = 0
    # ファイルが存在すればファイルを開く
    if os.path.isfile(race_url_file):
        with open(race_url_file, mode='r') as f:
            # ファイルをリストとして読み込む
            pre_url_num = len(f.readlines())
    # ファイルの行数と該当したWebページの件数が一致しているか
    if total_num != pre_url_num:
        # 一致していなければ書き込みモードでファイルを開く
        with open(race_url_file, mode='w') as f:
            # 取得行数
            total_file_rows = 0
            # エラーが出るまで無限ループ
            while True:
                # 5秒待機
                time.sleep(5)
                # ページ上のすべての要素が読み込まれるまで10秒待機
                wait.until(EC.presence_of_all_elements_located)
                # bodyのtrタグの要素数を取得
                table_rows = driver.find_element_by_class_name(
                    'race_table_01').find_elements_by_tag_name("tr")
                total_file_rows += len(table_rows) - 1
                # 行数分ループ
                for row in range(1, len(table_rows)):
                    # レース情報のリンクを取得し、ファイルに書き出し
                    race_link = table_rows[row].find_elements_by_tag_name(
                        "td")[4].find_element_by_tag_name("a").get_attribute("href")
                    f.write(race_link + "\n")
                try:
                    # ページを次に送る
                    target = driver.find_elements_by_link_text("次")[0]
                    # javascriptで強制的にクリック処理
                    driver.execute_script("arguments[0].click();", target)
                # エラーをキャッチしたらループを抜ける
                except IndexError:
                    break
        # 処理結果を出力
        logging.info(str(
            year) + "年" + str('{0:02d}'.format(month)) + "月のURL情報を" + str(total_file_rows) + "件取得しました")
    else:
        # 全てのデータを取得済の場合はログ出力のみ行う
        logging.info(str(year) + "年" +
                     str('{0:02d}'.format(month)) + "月までのURL情報は取得済のためスキップします")


if __name__ == '__main__':
    # ログフォーマットを定義
    formatter = "%(asctime)s [%(levelname)s]\t%(message)s"
    # ログファイルを定義
    logging.basicConfig(filename='log/activity.log',
                        level=logging.INFO, format=formatter)
    # 処理開始をログに出力
    logger.info("URL取得処理を開始します")
    # 処理開始
    get_race_url()
    # 処理終了をログに出力
    logger.info("URL取得処理を終了します")
