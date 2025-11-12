import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import os

# === Load environment variables ===
load_dotenv()

# === CONFIG ===
API_URL = "https://armatching-production.up.railway.app/reconcile"
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("Error: API_KEY not found!")
    print("Please create a .env file with: API_KEY=your-key-here")
    exit(1)

PATH_TO_FILE = 'G:\\My Drive\\Python\\BPAAS\\AR_Matching\\Test_Cases\\'
#PAYLOAD_FILE = PATH_TO_FILE+"test_cases_1_to_1.json"
PAYLOAD_FILE = PATH_TO_FILE+"test_final_comprehensive.json"

# === Load JSON from file ===
payload_path = Path(PAYLOAD_FILE)

if not payload_path.exists():
    print(f"Error: {PAYLOAD_FILE} not found!")
    print("   Create it with your test data (payments + open_items).")
    exit(1)

with open(payload_path, "r", encoding="utf-8") as f:
    payload = json.load(f)

print(f"Testing against: {API_URL}")
print(f"Loaded payload from {PAYLOAD_FILE}")
print(f"   Payments: {len(payload.get('payments', []))}")
print(f"   Open Items: {len(payload.get('open_items', []))}")
print("-" * 50)

# === Send to API ===
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

try:
    response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"API Error: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response: {e.response.text}")
    exit(1)

# === Pretty print result ===
result = response.json()
print("\nAPI Response:")
print(json.dumps(result, indent=2, ensure_ascii=False))

# === Summary - Use the API's summary field ===
summary = result.get("summary", {})

print("\n" + "=" * 50)
print(f"SUMMARY (Payments):")
print(f"  High Confidence:    {summary.get('high_confidence_payments', 0)}")
print(f"  HITL Review:        {summary.get('hitl_review_payments', 0)}")
print(f"  No Match:           {summary.get('no_match_payments', 0)}")
print(f"  Total Processed:    {summary.get('total_payments_processed', 0)}")
print("=" * 50)
print(f"SUMMARY (Match Records):")
print(f"  High Confidence:    {len(result.get('high_confidence', []))}")
print(f"  HITL Review:        {len(result.get('hitl_review', []))}")
print(f"  No Match:           {len(result.get('no_match', []))}")
print("=" * 50)
print(f"INVOICES:")
print(f"  No Match Invoices:  {summary.get('no_match_invoices', 0)}")
print(f"  Total Processed:    {summary.get('total_invoices_processed', 0)}")
print("=" * 50)
