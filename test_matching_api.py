import requests
import json
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
# === CONFIG ===
API_URL = "http://localhost:8000/reconcile"
API_KEY = os.getenv("API_KEY")  # Load from .env
PATH_TO_FILE = 'G:\\My Drive\\Python\\BPAAS\\AR_Matching\\Test_Cases\\'
#PAYLOAD_FILE = PATH_TO_FILE+"test_cases_1_to_1.json"  # Change this path if needed
PAYLOAD_FILE = PATH_TO_FILE+"test_json_vlaidation.json"  # Change this path if needed

# === Load JSON from file ===
payload_path = Path(PAYLOAD_FILE)

if not payload_path.exists():
    print(f"Error: {PAYLOAD_FILE} not found!")
    print("   Create it with your test data (payments + open_items).")
    exit(1)

with open(payload_path, "r", encoding="utf-8") as f:
    payload = json.load(f)

print(f"Loaded payload from {PAYLOAD_FILE}")
print(f"   Payments: {len(payload.get('payments', []))}")
print(f"   Open Items: {len(payload.get('open_items', []))}")
print("-" * 50)

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# === Send to API ===
try:
    response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"API Error: {e}")
    exit(1)

# === Pretty print result ===
result = response.json()
print("API Response:")
print(json.dumps(result, indent=2, ensure_ascii=False))

# === Optional: Summary ===
high = len(result.get("high_confidence", []))
hitl = len(result.get("hitl_review", []))
no = len(result.get("no_match", []))
