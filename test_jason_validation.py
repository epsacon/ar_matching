import requests
import json
from pathlib import Pathp

# === CONFIG ===
VALIDATE_URL = "http://localhost:8000/validate"
PATH_TO_FILE = 'G:\\My Drive\\Python\\BPAAS\\AR_Matching\\Test_Cases\\'
PAYLOAD_FILE = PATH_TO_FILE + "test_50_violations.json"

# === Load JSON from file ===
payload_path = Path(PAYLOAD_FILE)

if not payload_path.exists():
    print(f"Error: {PAYLOAD_FILE} not found!")
    print("   Create it with your test data (payments + open_items).")
    exit(1)

# ADD ERROR HANDLING FOR EMPTY/INVALID JSON
try:
    with open(payload_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

        if not content:
            print(f"Error: {PAYLOAD_FILE} is empty!")
            print("   Please add valid JSON content to the file.")
            exit(1)

        payload = json.loads(content)

except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON in {PAYLOAD_FILE}")
    print(f"   {str(e)}")
    print("   Please check your JSON syntax.")
    exit(1)
except Exception as e:
    print(f"Error reading file: {e}")
    exit(1)

print(f"Loaded payload from {PAYLOAD_FILE}")
print(f"   Payments: {len(payload.get('payments', []))}")
print(f"   Open Items: {len(payload.get('open_items', []))}")
print("=" * 60)

# === Send to Validation API (NO API KEY NEEDED) ===
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(VALIDATE_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"API Error: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response: {e.response.text}")
    exit(1)

# === Parse and Display Validation Result ===
result = response.json()

print("\n" + "=" * 60)
print("VALIDATION RESULT")
print("=" * 60)

if result.get("valid"):
    print("✅ " + result["message"])
    print("\nYour JSON is ready to send to /reconcile endpoint!")
else:
    print("❌ " + result["message"])

    if result.get("errors"):
        print("\n" + "-" * 60)
        print("ERRORS FOUND:")
        print("-" * 60)
        for i, error in enumerate(result["errors"], 1):
            print(f"\n{i}. Location: {error['location']}")
            print(f"   Type: {error['type']}")
            print(f"   Message: {error['message']}")
            if error.get('input_value'):
                print(f"   Input Value: {error['input_value']}")

    if result.get("suggestions"):
        print("\n" + "-" * 60)
        print("SUGGESTIONS TO FIX:")
        print("-" * 60)
        for i, suggestion in enumerate(result["suggestions"], 1):
            print(f"{i}. {suggestion}")

    if result.get("expected_format"):
        print("\n" + "-" * 60)
        print("EXPECTED FORMAT:")
        print("-" * 60)
        print(json.dumps(result["expected_format"], indent=2))

print("\n" + "=" * 60)