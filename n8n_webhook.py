import requests
import os
import json


def send_raw_files_for_sniffing(webhook_url, folder_path, file_list, auth_token):
    """
    Uploads files with NO metadata and GENERIC content-type headers.
    This forces n8n to rely on Magic Bytes detection.
    """
    # FIX: Initialize this BEFORE the try block so it exists if an error occurs immediately
    open_files = []

    try:
        headers = {'auth': auth_token}
        files_payload = []

        print(f"Preparing {len(file_list)} files for 'Blind' Upload...")

        for filename in file_list:
            file_path = os.path.join(folder_path, filename)

            if not os.path.exists(file_path):
                print(f"⚠️ Skipped (Not Found): {filename}")
                continue

            f = open(file_path, 'rb')
            open_files.append(f)

            # CRITICAL FOR TESTING:
            # We deliberately set Content-Type to 'application/octet-stream'.
            # This forces the n8n Sniffer Node to look at the magic bytes.
            files_payload.append(
                ('data', (filename, f, 'application/octet-stream'))
            )
            print(f"  -> Added: {filename} [As generic binary]")

        print(f"\nSending to n8n...")

        # Note: We are NOT sending the 'data=' parameter (metadata). Just files.
        response = requests.post(
            webhook_url,
            files=files_payload,
            headers=headers
        )

        # Cleanup success path
        for f in open_files:
            f.close()

        response.raise_for_status()
        print(f"✓ Success! Status: {response.status_code}")

        # Return JSON if possible, else text
        try:
            return response.json()
        except ValueError:
            return {"text_response": response.text}

    except Exception as e:
        # Cleanup error path
        # This is now safe because open_files was defined before 'try'
        for f in open_files:
            f.close()
        print(f"✗ Error: {e}")
        return None


if __name__ == "__main__":
    # --- CONFIGURATION ---
    AUTH_TOKEN = "michi1234"
    WEBHOOK_URL = "https://n8n.srv928636.hstgr.cloud/webhook-test/4c9301bd-d9f1-4761-b359-ef405dbc4195"

    LOCAL_FILE_PATH = "G:\\My Drive\\Python\\BPAAS\\ar_matching\\Test_Cases\\"

    # The Mix
    FILES_TO_SEND = [
        "open_invoices_no_header.csv",
        "payments_no_header.txt",
        "test_case.pdf",
        "test_case.xlsx",
        "check_example_3.jpg",
        "Check Example.png"
    ]

    # Run the test
    print(f"--- Starting Stress Test ---")
    result = send_raw_files_for_sniffing(WEBHOOK_URL, LOCAL_FILE_PATH, FILES_TO_SEND, AUTH_TOKEN)

    if result:
        print("\n=== Response from n8n ===")
        # Using json.dumps to make the output readable
        print(json.dumps(result, indent=2))