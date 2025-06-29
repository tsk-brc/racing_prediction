FROM --platform=linux/amd64 python:3.8-slim

# 必要なパッケージのインストール
RUN apt-get update && \
    apt-get install -y wget curl unzip && \
    # Firefoxのインストール（ESR版）
    apt-get install -y firefox-esr && \
    # geckodriverのインストール（固定バージョン）
    wget -O /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-linux64.tar.gz" && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/geckodriver && \
    rm /tmp/geckodriver.tar.gz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 必要なファイルをコピー
COPY requirements.txt ./
COPY . .

# Pythonパッケージのインストール
RUN pip install --no-cache-dir -r requirements.txt

# 必要なディレクトリを作成
RUN mkdir -p url log csv html

# デフォルトコマンド
CMD ["python", "get_race_url.py"] 