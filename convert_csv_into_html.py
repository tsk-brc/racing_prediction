# coding:utf-8

"""
htmlディレクトリに存在するHTMLファイルからCSVファイルを作成する
"""
import logging
from os import path
import os
import re
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import pytz
import time
import datetime
import configparser

# --------------------------------------------------
# configparserの宣言とiniファイルの読み込み
# --------------------------------------------------
config = configparser.ConfigParser()
config.read(os.getcwd() + '/config.ini', encoding='utf-8')
now_datetime = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))


OWN_FILE_NAME = path.splitext(path.basename(__file__))[0]
# htmlファイルが格納されているフォルダ
RACE_HTML_DIR = os.getcwd() + config.get('DIR', 'RACE_HTML_DIR')
# csvファイルを格納するフォルダ
CSV_DIR = os.getcwd() + config.get('DIR', 'CSV_DIR')
# ログファイル名
logger = logging.getLogger(__name__)
# CSVを作成する開始年
FROM_YEAR = config.getint('CONST', 'FROM_YEAR')

# レースデータのCSVフォーマット
race_data_columns = [
    # レースID(htmlのファイル名)
    'race_id',
    # レース番号
    'race_round',
    # レース名
    'race_name',
    # コース情報(ダート or 芝 + 右回り or 左回り + 距離)
    'race_course',
    # 天候
    'weather',
    # 馬場状態
    'ground_status',
    # 発走時間
    'time',
    # 開催日
    'date',
    # 開催情報(何回 + 競馬場 + 何日目)
    'race_information',
    # 頭数
    'total_horse_numbers',
    # 1着の枠番
    'bracket_number_in_first',
    # 1着の馬番
    'horse_number_in_first',
    # 2着の枠番
    'bracket_number_in_second',
    # 2着の馬番
    'horse_number_in_second',
    # 3着の枠番
    'bracket_number_in_third',
    # 3着の馬番
    'horse_number_in_third',
    # 単勝の払戻金
    'refund_for_win',
    # 複勝の払戻金
    'refund_for_first_place',
    'refund_for_second_place',
    'refund_for_third_place',
    # 枠連の払戻金
    'refund_for_bracket_quinella',
    # 馬連の払戻金
    'refund_for_quinella',
    # ワイドの払戻金
    'refund_for_quinella_place_for_first_place_and_second_place',
    'refund_for_quinella_place_for_first_place_and_third_place',
    'refund_for_quinella_place_for_second_place_and_third_place',
    # 馬単の払戻金
    'refund_for_exacta',
    # 3連複の払戻金
    'refund_for_trio',
    # 3連単の払戻金
    'refund_for_trifecta'
]

# 馬データのCSVフォーマット
horse_data_columns = [
    # レースID(htmlのファイル名)
    'race_id',
    # 順位
    'rank',
    # 枠番
    'bracket_number',
    # 馬番
    'horse_number',
    # 馬のキー番号
    'horse_id',
    # 性別 + 年齢
    'sex_and_age',
    # 斤量
    'jockey_weight',
    # 騎手のキー番号
    'jockey_id',
    # タイム
    'goal_time',
    # 着差
    'margin',
    # 通過順位
    'passed_rank',
    # 上りタイム
    'last_three_furlong_time',
    # 単勝オッズ
    'odds',
    # 何番人気か
    'popular',
    # 馬体重
    'horse_weight',
    # 調教師のキー番号
    'trainer_id',
    # 馬主のキー番号
    'owner_id'
]


def convert_csv_into_html():
    # 対象期間のデータを年単位でCSVに変換
    for year in range(FROM_YEAR, now_datetime.year + 1):
        convert_csv_into_html_by_year(year)


def convert_csv_into_html_by_year(year):
    # レースデータのCSVファイル名
    race_data_csv = CSV_DIR + "race-" + str(year) + ".csv"
    # 馬データのCSVファイル名
    horse_data_csv = CSV_DIR + "/horse-" + str(year) + ".csv"
    # ファイルが存在しなければ新規作成
    if not ((os.path.isfile(race_data_csv)) and (os.path.isfile(horse_data_csv))):
        # レースデータのデータフレームを作成
        race_df = pd.DataFrame(columns=race_data_columns)
        # 馬データのデータフレームを作成
        horse_df = pd.DataFrame(columns=horse_data_columns)
        logger.info(str(year) + "年のCSVファイルを新規作成します")
        #
        total = 0
        for month in range(1, 13):
            # 対象年月のhtmlフォルダ
            html_dir = RACE_HTML_DIR + \
                str(year) + "/" + str('{0:02d}'.format(month))
            # 対象年月のhtmlフォルダが存在する場合のみ処理を行う
            if os.path.isdir(html_dir):
                # ファイル一覧を取得
                file_list = os.listdir(html_dir)
                # ファイルのリスト数を加算
                total += len(file_list)
                logger.info(str(year) + "年" + str('{0:02d}'.format(month)) + "月のHTMLを" +
                            str(len(file_list)) + "件変換します")
                # ファイル一覧の数だけループ
                for file_name in file_list:
                    with open(html_dir + "/" + file_name, "r") as f:
                        html = f.read()
                        list = file_name.split(".")
                        race_id = list[-2]
                        race_list, horse_list_list = get_rade_and_horse_data_by_html(
                            race_id, html)
                        for horse_list in horse_list_list:
                            horse_se = pd.Series(
                                horse_list, index=horse_df.columns)
                            horse_df = horse_df.append(
                                horse_se, ignore_index=True)
                        race_se = pd.Series(race_list, index=race_df.columns)
                        race_df = race_df.append(race_se, ignore_index=True)
        # ヘッダーありインデックスなしでCSVを保存
        race_df.to_csv(race_data_csv, header=True, index=False)
        horse_df.to_csv(horse_data_csv, header=True, index=False)
        logger.info(
            "レースデータ" + str(race_df.shape[0]) + "行、" + str(race_df.shape[1]) + "列に変換しました")
        logger.info(
            "馬データ" + str(horse_df.shape[0]) + "行、" + str(horse_df.shape[1]) + "列に変換しました")
        logger.info(str(year) + "年のHTMLを" + str(total) + "件変換しました")
    else:
        # CSVファイルが存在する場合はログ出力のみ行う
        logger.info(str(year) + "年は存在するためスキップします")


def get_rade_and_horse_data_by_html(race_id, html):
    race_list = [race_id]
    horse_list_list = []
    # htmlパーサー
    parser = BeautifulSoup(html, 'html.parser')

    # レース情報を取得
    race_info = parser.find("div", class_="data_intro")
    # レース番号
    race_list.append(race_info.find(
        "dt").get_text().strip("\n"))
    # レース名
    race_list.append(race_info.find(
        "h1").get_text().strip("\n"))
    # pタグ内のレース情報
    race_details1 = race_info.find(
        "p").get_text().strip("\n").split("\xa0/\xa0")
    # コース情報
    race_list.append(race_details1[0])
    # 天候
    race_list.append(race_details1[1])
    # 馬場状態
    race_list.append(race_details1[2])
    # 発走時間
    race_list.append(race_details1[3])
    race_details2 = race_info.find(
        "p", class_="smalltxt").get_text().strip("\n").split(" ")
    # 開催日
    race_list.append(race_details2[0])
    # 開催情報
    race_list.append(race_details2[1])

    result_rows = parser.find(
        "table", class_="race_table_01 nk_tb_common").findAll('tr')  # レース結果
    # 上位3着の情報
    race_list.append(len(result_rows)-1)  # total_horse_numbers
    for i in range(1, 4):
        row = result_rows[i].findAll('td')
        # bracket_number_in_first or second or third
        race_list.append(row[1].get_text())
        # horse_number_in_first or second or third
        race_list.append(row[2].get_text())

    # 払い戻し(単勝・複勝・三連複・3連単)
    pay_back_tables = parser.findAll("table", class_="pay_table_01")

    pay_back1 = pay_back_tables[0].findAll('tr')  # 払い戻し1(単勝・複勝)
    race_list.append(pay_back1[0].find(
        "td", class_="txt_r").get_text())  # refund_for_win
    hukuren = pay_back1[1].find("td", class_="txt_r")
    tmp = []
    for string in hukuren.strings:
        tmp.append(string)
    for i in range(3):
        try:
            # refund_for_first_place or refund_for_second_place or refund_for_third_place
            race_list.append(tmp[i])
        except IndexError:
            race_list.append("0")

    # 枠連
    try:
        race_list.append(pay_back1[2].find("td", class_="txt_r").get_text())
    except IndexError:
        race_list.append("0")

    # 馬連
    try:
        race_list.append(pay_back1[3].find("td", class_="txt_r").get_text())
    except IndexError:
        race_list.append("0")
    # 払い戻し2(三連複・3連単)
    pay_back2 = pay_back_tables[1].findAll('tr')

    # wide 1&2
    wide = pay_back2[0].find("td", class_="txt_r")
    tmp = []
    for string in wide.strings:
        tmp.append(string)
    for i in range(3):
        try:
            race_list.append(tmp[i])
        except IndexError:
            race_list.append("0")
    try:
        # 馬単の払戻金
        race_list.append(pay_back2[1].find(
            "td", class_="txt_r").get_text())
        # 3連複の払戻金
        race_list.append(pay_back2[2].find(
            "td", class_="txt_r").get_text())
        # 3連単の払戻金
        race_list.append(pay_back2[3].find(
            "td", class_="txt_r").get_text())
    except IndexError:
        race_list.append("0")

    # horse data
    for rank in range(1, len(result_rows)):
        horse_list = [race_id]
        result_row = result_rows[rank].findAll("td")
        # 順位
        horse_list.append(result_row[0].get_text())
        # 枠番
        horse_list.append(result_row[1].get_text())
        # 馬番
        horse_list.append(result_row[2].get_text())
        # 馬のキー番号
        horse_list.append(result_row[3].find('a').get('href').split("/")[-2])
        # 性別 + 年齢
        horse_list.append(result_row[4].get_text())
        # 斤量
        horse_list.append(result_row[5].get_text())
        # 騎手のキー番号
        horse_list.append(result_row[6].find('a').get('href').split("/")[-2])
        # タイム
        horse_list.append(result_row[7].get_text())
        # 着差
        horse_list.append(result_row[8].get_text())
        # 9:タイム指数は取得しない
        # 通過順位
        horse_list.append(result_row[10].get_text())
        # 上りタイム
        horse_list.append(result_row[11].get_text())
        # 単勝オッズ
        horse_list.append(result_row[12].get_text())
        # 何番人気か
        horse_list.append(result_row[13].get_text())
        # 馬体重
        horse_list.append(result_row[14].get_text())
        # 15:調教タイム、16:厩舎コメント、17:備考は取得しない
        # 調教師のキー番号
        horse_list.append(result_row[18].find('a').get('href').split("/")[-2])
        # 馬主のキー番号
        horse_list.append(result_row[19].find('a').get('href').split("/")[-2])

        horse_list_list.append(horse_list)

    return race_list, horse_list_list


if __name__ == '__main__':
    # ログフォーマットを定義
    formatter = "%(asctime)s [%(levelname)s]\t%(message)s"
    # ログファイルを定義
    logging.basicConfig(filename='log/activity.log',
                        level=logging.INFO, format=formatter)
    # 処理開始をログに出力
    logger.info("CSV作成処理を開始します")
    # 処理開始
    convert_csv_into_html()
    # 処理終了をログに出力
    logger.info("CSV作成処理を終了します")
