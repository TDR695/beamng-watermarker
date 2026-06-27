from flask import Flask, request, send_file
import zipfile
import requests
import io
import os

app = Flask(__name__)

# SECURE: The link is hidden! It reads directly from Render's private vault at runtime.
DROPBOX_DIRECT_URL = os.environ.get("DROPBOX_LINK")

@app.route('/', defaults={'path': ''}, methods=['POST', 'GET'])
@app.route('/<path:path>', methods=['POST', 'GET'])
def catch_all(path):
    # If the system can't find your hidden link, throw an error immediately
    if not DROPBOX_DIRECT_URL:
        return "Server Configuration Error: Storage link missing.", 500

    buyer_email = "test_buyer@gmail.com"
    order_id = "123456"
    
    if request.is_json:
        data = request.get_json(silent=True) or {}
        buyer_email = data.get('email', buyer_email)
        order_id = data.get('order_id', order_id)

    try:
        response = requests.get(DROPBOX_DIRECT_URL, stream=True)
        if response.status_code != 200:
            return "Error pulling asset data from Dropbox storage.", 500
            
        memory_zip = io.BytesIO(response.content)
        
        with zipfile.ZipFile(memory_zip, 'a') as zipf:
            watermark_text = f"Buyer: {buyer_email}\nOrder: {order_id}"
            zipf.writestr("vehicles/audi6/license.txt", watermark_text)
            
        memory_zip.seek(0)
        
        return send_file(
            memory_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name="audi6_fastlane_kajto.zip"
        )
        
    except Exception as e:
        return f"Server process encountered an issue: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)