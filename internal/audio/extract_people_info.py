import argparse
import re
import csv
import requests
from bs4 import BeautifulSoup
import time
import yaml

# config.yamlを読み込む関数
def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

# Simple regex patterns for extracting actor names (supports Japanese and English)
ACTOR_PATTERNS = [
    r"出演[:：]\s*([\w\u3000-\u30FF\u4E00-\u9FFF\uFF66-\uFF9F\s、,]+)", # Japanese
    r"Starring[:：]?\s*([\w\s,]+)", # English
    r"出演者[:：]?\s*([\w\s,\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF]+)", # Japanese
    r"Cast[:：]?\s*([\w\s,]+)", # English
]

# Wikipedia API
WIKI_API_JA = "https://ja.wikipedia.org/w/api.php"
WIKI_API_EN = "https://en.wikipedia.org/w/api.php"


def extract_names(description):
    names = set()
    for pat in ACTOR_PATTERNS:
        m = re.search(pat, description)
        if m:
            # 区切り文字で分割
            for n in re.split(r"[、,\s]+", m.group(1)):
                n = n.strip()
                if n:
                    names.add(n)
    return list(names)


def search_wikipedia(name, lang='ja'):
    # lang: 'ja' or 'en'
    api = WIKI_API_JA if lang == 'ja' else WIKI_API_EN
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': name,
        'format': 'json',
    }
    r = requests.get(api, params=params)
    data = r.json()
    if data['query']['search']:
        page_title = data['query']['search'][0]['title']
        url = f"https://{lang}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
        return url
    return None


def extract_profile_from_wikipedia(url, lang='ja'):
    # 年齢・性別の推定
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        text = infobox.get_text() if infobox else soup.get_text()
        # 年齢
        age = None
        # 日本語
        age_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        # 英語
        if not age_match:
            age_match = re.search(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", text)
            if age_match:
                birth_year = int(age_match.group(3))
                age = time.localtime().tm_year - birth_year
        if age_match and not age:
            birth_year = int(age_match.group(1))
            age = time.localtime().tm_year - birth_year
        # 性別
        gender = None
        if lang == 'ja':
            for g in ["男性", "女性", "男優", "女優", "俳優", "女優"]:
                if g in text:
                    gender = "男" if g in ["男性", "男優", "俳優"] else "女"
                    break
        else:
            for g in ["male", "female", "actor", "actress"]:
                if g in text.lower():
                    gender = "男" if g in ["male", "actor"] else "女"
                    break
        return age, gender
    except Exception:
        return None, None


def validate_config(config):
    required = ['people_metadata_csv', 'python_path']
    missing = [k for k in required if not config.get(k)]
    if missing:
        exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desc', required=True, help='動画説明文')
    parser.add_argument('--output', default=None, help='保存先CSV')
    parser.add_argument('--config', default='config.yaml', help='設定ファイルパス')
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)
    output_csv = args.output or config.get('people_metadata_csv', 'models/people_metadata.csv')
    output_dir = os.path.dirname(output_csv)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    names = extract_names(args.desc)

    records = []
    for name in names:
        wiki_url = search_wikipedia(name, lang='ja')
        age, gender = None, None
        if wiki_url:
            age, gender = extract_profile_from_wikipedia(wiki_url, lang='ja')
        if not wiki_url or (age is None and gender is None):
            wiki_url_en = search_wikipedia(name, lang='en')
            if wiki_url_en:
                age_en, gender_en = extract_profile_from_wikipedia(wiki_url_en, lang='en')
                if wiki_url is None:
                    wiki_url = wiki_url_en
                if age is None:
                    age = age_en
                if gender is None:
                    gender = gender_en
        records.append({
            'name': name,
            'age': age if age else '',
            'gender': gender if gender else '',
            'wiki': wiki_url if wiki_url else '',
            'timestamp': time.strftime('%Y-%m-%d')
        })

    existing = set()
    if os.path.exists(output_csv):
        with open(output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row['name'], row['wiki'], row['timestamp'])
                existing.add(key)

    with open(output_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'age', 'gender', 'wiki', 'timestamp'])
        if f.tell() == 0:
            writer.writeheader()
        for rec in records:
            key = (rec['name'], rec['wiki'], rec['timestamp'])
            if key in existing:
                continue
            writer.writerow(rec)


if __name__ == '__main__':
    main()
