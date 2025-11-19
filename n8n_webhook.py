import requests
import os


def send_files_to_webhook(webhook_url, invoices_path, payments_path, auth_token):
    """
    Send both files to a single n8n webhook
    """
    try:
        headers = {'auth': auth_token}

        with open(invoices_path, 'rb') as inv_file, open(payments_path, 'rb') as pay_file:
            files = {
                'invoices': (os.path.basename(invoices_path), inv_file, 'text/csv'),
                'payments': (os.path.basename(payments_path), pay_file, 'text/csv')
            }

            print(f"Sending both files to {webhook_url}...")
            response = requests.post(webhook_url, files=files, headers=headers)
            response.raise_for_status()

            print(f"✓ Success! Status: {response.status_code}")
            return response.json() if response.text else {"status": "success"}

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


if __name__ == "__main__":
    AUTH_TOKEN = "michi1234"
    WEBHOOK_URL = "https://n8n.srv928636.hstgr.cloud/webhook-test/4c9301bd-d9f1-4761-b359-ef405dbc4195"

    LOCAL_FILE_PATH = "G:\\My Drive\\Python\\BPAAS\\ar_matching\\Test_Cases\\"
    INVOICES_FILE = "open_invoices_no_header.csv"
    PAYMENTS_FILE = "payments_no_header.csv"

    invoices_full_path = os.path.join(LOCAL_FILE_PATH, INVOICES_FILE)
    payments_full_path = os.path.join(LOCAL_FILE_PATH, PAYMENTS_FILE)

    print("\n=== Uploading Both Files ===")
    result = send_files_to_webhook(WEBHOOK_URL, invoices_full_path, payments_full_path, AUTH_TOKEN)
    if result:
        print("Response:", result)

    print("\n=== Done ===")