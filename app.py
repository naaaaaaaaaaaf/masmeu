# coding=utf-8
import requests
import json
import time
import os
import random
import urllib.parse
import re
import xmltodict
import threading
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
print(config['mastodon']['domain'])
meu = ["か゛ら゛出゛て゛く゛る゛め゛う゛〜゛〜゛〜゛！゛！゛","に゛入゛っ゛て゛く゛る゛め゛う゛ー゛！゛！゛！゛！゛！゛"]
pass_rules = [
    ["接頭辞", "名詞"],
    ["形容詞", "名詞"],  # ~なxxx
    ["名詞", "特殊", "名詞"],
    ["助動詞,助動詞する", "名詞"],  # ~するxxx
    ["動詞", "名詞"],  # ~するxxx
    ["助詞,助詞連体化", "名詞"],  # のxxx
    ["形容詞,形容,連用テ接続", "動詞", "助動詞,助動詞た", "名詞"],  # ~な-したxxx
    ["名詞", "助詞,格助詞,*,と,と,と", "動詞", "名詞"],  # xxxと~するyyy
    ["名詞", "助詞,格助詞,*,と,と,と", "名詞"],  # xxxとyyy
    ["形容動詞,形動", "助動詞,助動詞だ,体言接続,な,な,だ", "名詞"],  # ~なxxx
    ["名詞", "助詞,並立助詞"],  # xxxとか
]
# combined_rules = []

# t = requests.get("https://api.tachibana.cool/v1/imas/dict.json?type=noun")
# combined_rules += t.json()["data"] if t.status_code == 200 else []

# combined_rules = [x for x in combined_rules if " " not in x]

def normalizeText(text):
    # メンション/RT除去
    if "@" in text:
        return False
    p = re.compile(r"<[^>]*?>")
    text = p.sub("", text)
    # URL除去
    return re.sub("http(|s)://.+?(\s|$)", r"\2", text)


def getAPI(text, appid):
    url = "https://jlp.yahooapis.jp/MAService/V1/parse?appid={}&results=ma,uniq&sentence={}&response=surface,reading,feature".format(
        appid, urllib.parse.quote(text))
    t = requests.get(url)

    if t.status_code != 200:
        return False

    result = xmltodict.parse(t.text).get("ResultSet")
    return result["ma_result"]["word_list"]["word"] if result else False


def checkStrict(i, data):
    for patterns in pass_rules:
        nodes = data[i - len(patterns) + 1:i] + data[i:i + len(patterns)]

        for j, node in enumerate(nodes):
            if node["feature"].startswith(patterns[0]):
                for x, y in zip(nodes[j + 1:], patterns[1:]):
                    if not x["feature"].startswith(y):
                        break
                else:
                    return True
            # 半分に折り返したらbreak
            if len([k for k in ["surface", "reading", "feature"] if node[k] == data[i][k]]) == 3:
                break
    return False


def filterWords(data, text):
    words = []

    brackets, start_blacket = False, False
    for i, node in enumerate(data):
        if isinstance(node, (list, tuple)):
            return False
        # 特殊文字(改行等)ならcontinue
        if node["feature"].startswith("特殊,単漢"):
            continue
        # 空白を置換
        if node["feature"].startswith("特殊,空白"):
            node["surface"] = " "
        # 強制結合ルールの適用
        if True:  # if not [x for x in combined_rules if node["surface"] in x]:
            # 名詞でないなら前後の関係も厳密に吟味するワードフィルターにかける
            if not node["feature"].startswith("名詞") and not checkStrict(i, data) and not brackets:
                continue

        # ワードフィルターを通過した単語を追加
        # 前の名詞と連続している場合か括弧の連続は足し合わせて追加 (Need fix: 分割された単語が小さい場合は問題が発生することがある)
        if (words and words[-1] + node["surface"] in text) or brackets and not start_blacket:
            words[-1] += node["surface"]
        else:
            words.append(node["surface"])
            start_blacket = False
    if not words:
        return False

    # 1文字なら破棄し, ハッシュタグの条件を満たす
    return [" {} ".format(x) if x.startswith("#") else x for x in words if len(x) > 1]


def choose(words):
    return random.choice(words) + 'はめうのお尻に入らないめう…' if random.randint(1,4) == 1 else '゛'.join(list(max(words, key=len))) + '゛が゛め゛う゛の゛お゛尻゛'+ random.choice(meu)

def post_toot(domain, access_token, params):
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    url = "https://{}/api/v1/statuses".format(domain)
    response = requests.post(url, headers=headers, json=params)
    if response.status_code != 200:
        raise Exception('リクエストに失敗しました。')
    return response

def get_toot(domain, access_token, params):
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    url = "https://{}//api/v1/timelines/public".format(domain)
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception('リクエストに失敗しました。')
    return response

def worker():
    #mastodon = login()
    #t = mastodon.timeline_public(max_id=None, since_id=None, limit=100)
    t = get_toot(config['mastodon']['domain'], config['mastodon']['access_token'], {'limit': 100})
    #random.shuffle(t)
    t = t.json()
    for tweet in t:
        if tweet["favourited"]:
            continue

        text = normalizeText(tweet["content"])
        if not text:
            continue
        data = getAPI(text, config['yahoo']['access_token'])
        if not data:
            continue
        words = filterWords(data, text)
        if not words:
            continue
        toot = choose(words)
        print(toot)
        print(tweet["id"])
        # mastodon.status_favourite(tweet["id"])
        # mastodon.status_post(toot, in_reply_to_id=None, media_ids=None, sensitive=False, visibility='unlisted', spoiler_text=None)
        post_toot(config['mastodon']['domain'], config['mastodon']['access_token'], {'status': toot, 'visibility': 'unlisted'})
        break

def schedule(f, interval=1200, wait=True):
    base_time = time.time()
    next_time = 0
    while True:
        t = threading.Thread(target=f)
        t.start()
        if wait:
            t.join()
        next_time = ((base_time - time.time()) % interval) or interval
        time.sleep(next_time)

if __name__ == "__main__":
    # 定期実行部分
    schedule(worker)
