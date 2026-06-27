import os
import io
import requests
import zipfile
import tempfile
import gc  # Garbage Collector to forcefully clear RAM
from flask import Flask, request, send_file

app = Flask(__name__)

DROPBOX_DIRECT_URL = os.environ.get("DROPBOX_LINK")

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
        # 1. Create a temporary file path manually to have total control
        fd, temp_file_path = tempfile.mkstemp(dir="/tmp")
        os.close(fd) # Close the file descriptor immediately so requests can write to it cleanly

        # 2. Download directly to disk using a small stream buffer
        with requests.get(DROPBOX_DIRECT_URL, stream=True) as response:
            if response.status_code != 200:
                return "Error pulling asset data from Dropbox storage.", 500
            
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096): # Tiny 4KB chunks
                    if chunk:
                        f.write(chunk)
                        f.flush() # Force write to disk, keeping RAM completely empty

        # 3. Open zip, write the small text watermark, and close it immediately
        with zipfile.ZipFile(temp_file_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
            watermark_text = f"Buyer: {buyer_email}\nOrder: {order_id}"
            zipf.writestr("vehicles/audi6/license.txt", watermark_text)

        # 4. CRITICAL: Force Python to purge any residual RAM usage before sending
        gc.collect()

        # 5. Send the file using conditional streaming
        response_file = send_file(
            temp_file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name="audi6_fastlane_kajto.zip"
        )
        
        # Tell Render to delete the file AFTER it has finished downloading to the customer
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
