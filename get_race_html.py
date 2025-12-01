# coding:utf-8
"""
urlディレクトリに存在する情報からHTMLファイルを取得する
"""
import configparser
import datetime
import logging
import os
import time
from os import path

import pytz
import requests
from bs4 import BeautifulSoup

config = configparser.ConfigParser()
config.read(os.getcwd() + "/config.ini", encoding="utf-8")

now_datetime = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))


OWN_FILE_NAME = path.splitext(path.basename(__file__))[0]
# URL情報が格納されているフォルダ
RACE_URL_DIR = os.getcwd() + config.get("DIR", "RACE_URL_DIR")
# 取得したhtmlを格納するフォルダ
RACE_HTML_DIR = os.getcwd() + config.get("DIR", "RACE_HTML_DIR")
# ログファイル名
logger = logging.getLogger(__name__)
# HTMLを作成する開始年
FROM_YEAR = config.getint("CONST", "FROM_YEAR")


def get_race_html():
    # 昨年までのデータを取得
    for year in range(FROM_YEAR, now_datetime.year):
        for month in range(1, 13):
            get_race_html_by_year_and_month(year, month)
    # 今年のデータを取得
    for year in range(now_datetime.year, now_datetime.year + 1):
        for month in range(1, now_datetime.month + 1):
            get_race_html_by_year_and_month(year, month)


def get_race_html_by_year_and_month(year, month):
    # 対象年のファイルを開く
    with open(
        RACE_URL_DIR + str(year) + str("{0:02d}".format(month)) + ".txt", "r"
    ) as f:
        # HTMLを保存するフォルダ(/html/yyyy/mm 配下に保存)
        save_dir = RACE_HTML_DIR + str(year) + "/" + str("{0:02d}".format(month))
        # フォルダが存在しなければ新規作成
        if not os.path.isdir(save_dir):
            os.makedirs(save_dir)
        # URLを取得
        urls = f.read().splitlines()
        # 現在保持しているHTMLのリストを取得
        file_list = os.listdir(save_dir)
        # 保持しているHTMLの数と取得対象のHTMLの数が異なる場合のみ処理を行う
        if len(urls) != len(file_list):
            logger.info(
                str(year) + "年" + str("{0:02d}".format(month)) + "月のHTMLを取得します"
            )
            for url in urls:
                # URLをスラッシュ区切りで格納
                list = url.split("/")
                # レースIDを取得
                race_id = list[-2]
                # 保存するファイル名
                save_file_path = save_dir + "/" + race_id + ".html"
                # 対象のファイルが存在しなければ取得
                if not os.path.isfile(save_file_path):
                    # ブラウザのようなヘッダーを設定
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Referer': 'https://db.netkeiba.com/',
                    }
                    # レスポンスを取得
                    response = requests.get(url, headers=headers, timeout=30)
                    # エンコーディングを行う
                    response.encoding = response.apparent_encoding
                    # レスポンスをテキスト形式で取得
                    html = response.text
                    # 5秒待機
                    time.sleep(5)
                    # HTMLを保存
                    with open(save_file_path, "w") as file:
                        file.write(html)
            # 処理結果を出力
            logging.info(
                str(year)
                + "年"
                + str("{0:02d}".format(month))
                + "月のHTMLを"
                + str(len(urls))
                + "件保存しました"
            )
        else:
            # 全てのデータを取得済の場合はログ出力のみ行う
            logging.info(
                str(year)
                + "年"
                + str("{0:02d}".format(month))
                + "月のHTMLは取得済のためスキップします"
            )


if __name__ == "__main__":
    # ログフォーマットを定義
    formatter = "%(asctime)s [%(levelname)s]\t%(message)s"
    # ログファイルを定義
    logging.basicConfig(
        filename="log/activity.log", level=logging.INFO, format=formatter
    )
    # 処理開始をログに出力
    logger.info("HTML取得処理を開始します")
    # 処理開始
    get_race_html()
    # 処理終了をログに出力
    logger.info("HTML取得処理を終了します")
