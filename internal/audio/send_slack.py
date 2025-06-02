import requests
import sys
import argparse
import yaml

def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

def send_slack(webhook_url, message):
    resp = requests.post(webhook_url, json={"text": message})
    return resp.status_code, resp.text

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', required=True)
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()
    config = load_config(args.config)
    webhook = config.get('slack_webhook_url', '')
    if not webhook:
        print("[Slack通知エラー] webhook_url未設定")
        sys.exit(1)
    code, resp = send_slack(webhook, args.message)
    print(f"[Slack通知] status={code}, resp={resp}")
    sys.exit(0 if code == 200 else 1)
