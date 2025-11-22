import requests
import json
import os
import concurrent.futures
import time

# ==========================================
# CONFIGURATION
# ==========================================
BASE_URL = "http://localhost:7860"
FLOW_ID = "d219696c-1776-4121-94b0-09ae69785d75"
ROUTER_COMPONENT_ID = "CustomComponent-4b8im"
API_KEY = "sk-zlfFD8dbElsOWeyskio_qQ7ACVRbh628kOlzkTRQMww"

# DEFINING YOUR PATHS
# Using r"" (raw string) is often safer, but your double backslash method works perfectly too.
BASE_PATH = r'G:\My Drive\python\BPAAS\ar_matching\Test_Cases'

FILES_TO_PROCESS = [
    os.path.join(BASE_PATH, "open_invoices_no_header.csv"),
    os.path.join(BASE_PATH, "payments_no_header.csv"),
]


# ==========================================
# SINGLE FILE WORKER (The Logic)
# ==========================================
def process_single_file(file_path):
    """
    This function runs in its own thread.
    It performs the full Upload -> Run cycle for one file.
    """
    filename = os.path.basename(file_path)
    print(f"🔵 [Start] {filename}")

    # --- STEP 1: UPLOAD ---
    upload_url = f"{BASE_URL}/api/v1/files/upload/{FLOW_ID}"
    headers = {"x-api-key": API_KEY} if API_KEY else {}

    try:
        if not os.path.exists(file_path):
            return f"❌ {filename}: File not found at {file_path}"

        with open(file_path, 'rb') as f:
            # Uploading...
            up_res = requests.post(upload_url, headers=headers, files={'file': f})

        if up_res.status_code not in [200, 201]:
            return f"❌ {filename}: Upload Failed ({up_res.status_code})"

        server_path = up_res.json().get("file_path")

    except Exception as e:
        return f"❌ {filename}: Upload Error ({str(e)})"

    # --- STEP 2: RUN FLOW ---
    run_url = f"{BASE_URL}/api/v1/run/{FLOW_ID}"

    payload = {
        "input_value": f"Process file: {filename}",
        "input_type": "chat",
        "tweaks": {
            ROUTER_COMPONENT_ID: {
                "file_path": server_path
            }
        }
    }

    run_headers = {"Content-Type": "application/json"}
    if API_KEY:
        run_headers["x-api-key"] = API_KEY

    try:
        # Running AI...
        run_res = requests.post(run_url, json=payload, headers=run_headers)

        if run_res.status_code == 200:
            return f"✅ [Done] {filename}: Success!"
        else:
            return f"⚠️ {filename}: Flow Error ({run_res.status_code})"

    except Exception as e:
        return f"❌ {filename}: Run Error ({str(e)})"


# ==========================================
# MAIN (Parallel Execution)
# ==========================================
if __name__ == "__main__":
    print(f"🚀 Launching {len(FILES_TO_PROCESS)} parallel requests...")
    print(f"📂 Reading from: {BASE_PATH}")

    # Quick validation before starting threads
    if not os.path.exists(BASE_PATH):
        print(f"❌ Error: The directory '{BASE_PATH}' does not exist.")
        print("   Please check if your G: drive is mounted correctly.")
        exit()

    start_time = time.time()

    # The Magic: ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_file = {executor.submit(process_single_file, f): f for f in FILES_TO_PROCESS}

        for future in concurrent.futures.as_completed(future_to_file):
            result = future.result()
            print(result)

    duration = time.time() - start_time
    print(f"\n🏁 All finished in {duration:.2f} seconds.")