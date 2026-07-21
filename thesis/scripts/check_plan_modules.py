"""
Quick script: creates an instance of the 'Insurance consents api test V3.0.0'
plan using config_template_consents_v3.json and prints the full response,
to check the exact module names before running the full automation.
"""

import json
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost:8443"
PLAN_NAME = "Insurance consents api test V3.0.0"
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "config_template_consents_v3.json"


def main():
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    r = requests.post(
        f"{BASE_URL}/api/plan",
        params={"planName": PLAN_NAME},
        json=config,
        verify=False,
        timeout=30,
    )

    print(f"HTTP status: {r.status_code}")
    print()

    if not r.ok:
        print("Response (error):")
        print(r.text)
        return

    data = r.json()
    print("Full response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print()
    print("=== Module names ===")
    for m in data.get("modules", []):
        print(f"- {m.get('testModule')}  (variant={m.get('variant')})")


if __name__ == "__main__":
    main()
