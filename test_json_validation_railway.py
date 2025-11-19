import json
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
API_URL = "https://armatching-production.up.railway.app/validate"
API_KEY = os.getenv("API_KEY")

PATH_TO_FILE = 'G:\\My Drive\\Python\\BPAAS\\AR_Matching\\Test_Cases\\'
PAYLOAD_FILE = PATH_TO_FILE + "test_50_violations.json"

# === Load JSON ===
with open(Path(PAYLOAD_FILE), "r", encoding="utf-8") as f:
    payload = json.loads(f.read())

# === Send to Railway ===
response = requests.post(
    API_URL,
    json=payload,
    headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
    timeout=30
)

# === Raw output only ===
print(json.dumps(response.json(), indent=2))