import logging
import configparser
import os
import datetime
import pytz
import pandas as pd

# 設定ファイルの読み込み
config = configparser.ConfigParser()
config.read(os.path.join(os.getcwd(), 'config.ini'), encoding='utf-8')

# CSVファイルを読み込む開始年
FROM_YEAR = config.getint('CONST', 'FROM_YEAR')
CURRENT_YEAR = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).year

# csvファイルを格納するフォルダ
CSV_DIR = os.getcwd() + config.get('DIR', 'CSV_DIR')

# ログファイル名
logger = logging.getLogger(__name__)

def csv_cleansing():
    # 複数のCSVファイルを読み込み、統合
    all_horse_data = []
    all_race_data = []

    for year in range(FROM_YEAR, CURRENT_YEAR + 1):
        horse_file_path = f'{CSV_DIR}horse-{year}.csv'
        race_file_path = f'{CSV_DIR}race-{year}.csv'

        # ファイルが存在する場合のみ読み込み
        if os.path.exists(horse_file_path):
            horse_data = pd.read_csv(horse_file_path, low_memory=False)
            # horse_weight列を文字列に変換
            horse_data['horse_weight'] = horse_data['horse_weight'].astype(str)
            # horse_weightを数値と変動に分割
            horse_data['weight_numeric'] = horse_data['horse_weight'].str.extract('(\d+)').astype(float)
            # 変動値の抽出、NaNの処理と整数型への変換
            horse_data['weight_change'] = horse_data['horse_weight'].str.extract('\(([^)]*)\)').fillna('0').replace('', '0').astype(int)
            # 欠損値の処理
            horse_data.fillna({'margin': 'unknown', 'passed_rank': 'unknown'}, inplace=True)
            all_horse_data.append(horse_data)

        if os.path.exists(race_file_path):
            race_data = pd.read_csv(race_file_path, low_memory=False)
            # 金額関連のデータを数値に変換
            columns_to_convert = [col for col in race_data.columns if 'refund' in col]
            for col in columns_to_convert:
                race_data[col] = race_data[col].str.replace(',', '').astype(float)
            all_race_data.append(race_data)

    # 全データの結合
    combined_horse_data = pd.concat(all_horse_data, ignore_index=True)
    combined_race_data = pd.concat(all_race_data, ignore_index=True)

    # データの統合
    combined_data = pd.merge(combined_horse_data, combined_race_data, on='race_id', how='left')

    # データをCSVファイルとして保存
    combined_data.to_csv(CSV_DIR + 'processed_data.csv', index=False)

if __name__ == '__main__':
    # ログフォーマットを定義
    formatter = "%(asctime)s [%(levelname)s]\t%(message)s"
    # ログファイルを定義
    logging.basicConfig(filename='log/activity.log',
                        level=logging.INFO, format=formatter)
    # 処理開始をログに出力
    logger.info("データクレンジング処理を開始します")
    # 処理開始
    csv_cleansing()
    # 処理終了をログに出力
    logger.info("データクレンジング処理を終了します")