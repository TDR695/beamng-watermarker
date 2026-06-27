import os
import io
import requests
import zipfile
import tempfile
import gc
import threading
from flask import Flask, request, send_file

app = Flask(__name__)

DROPBOX_DIRECT_URL = os.environ.get("DROPBOX_LINK")

def download_file_worker(url, target_path, success_event):
    """Downloads the heavy file in a separate thread so Flask never freezes."""
    try:
        with requests.get(url, stream=True) as response:
            if response.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                success_event.set() # Signal that download completed successfully
    except Exception:
        pass

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def catch_all(path):
    if not DROPBOX_DIRECT_URL:
        return "Server Configuration Error: Storage link missing.", 500

    buyer_email = "test_buyer@gmail.com"
    order_id = "123456"
    
    if request.is_json:
        data = request.get_json(silent=True) or {}
        buyer_email = data.get('email', buyer_email)
        order_id = data.get('order_id', order_id)

    temp_file_path = None

    try:
        # 1. Prepare manual temp file
        fd, temp_file_path = tempfile.mkstemp(dir="/tmp")
        os.close(fd)

        # 2. Start the download in a background thread
        download_success = threading.Event()
        download_thread = threading.Thread(
            target=download_file_worker, 
            args=(DROPBOX_DIRECT_URL, temp_file_path, download_success)
        )
        download_thread.start()

        # 3. Wait for the thread to finish (up to 10 minutes)
        # This keeps the request alive but lets Gunicorn breathe and handle port scanning
        completed = download_success.wait(timeout=600) 

        if not completed or os.path.getsize(temp_file_path) == 0:
            raise TimeoutError("The file download from storage timed out or failed.")

        # 4. Open zip and append the license text file directly on disk
        with zipfile.ZipFile(temp_file_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
            watermark_text = f"Buyer: {buyer_email}\nOrder: {order_id}"
            zipf.writestr("vehicles/audi6/license.txt", watermark_text)

        gc.collect()

        # 5. Send the file back to the buyer
        response_file = send_file(
            temp_file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name="audi6_fastlane_kajto.zip"
        )
        
        @response_file.call_on_close
        def cleanup():
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

        return response_file
        
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
        return f"Server process encountered an issue: {str(e)}", 500
