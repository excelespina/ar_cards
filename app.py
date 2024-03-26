from flask import Flask, render_template, jsonify, Response
import firebase_admin, requests
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# Initialize Firebase Admin
cred = credentials.Certificate("service_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

default_img = "https://upload.wikimedia.org/wikipedia/en/2/2e/PiLFirstIssue.jpg"

@app.route('/proxy/<path:url>')
def proxy(url):
    # Decode the URL path
    decoded_url = requests.utils.unquote(url)
    # Make a request to the actual resource
    response = requests.get(decoded_url)
    # Forward the response content type and body to the client
    return Response(response.content, content_type=response.headers['Content-Type'])

@app.route('/ar/content/<id>')
def get_content_by_id(id):
    # Example direct return, replace with actual Firestore fetching logic if needed
    content_info = {
        "type": "image",
        "file": default_img
    }
    return jsonify(content_info)

@app.route('/ar')
@app.route('/ar/<id>')
def ar(id=None):
    now = datetime.now(timezone.utc)
    content_map = {}

    if id:
        doc_ref = db.collection('events').document(id)
        doc = doc_ref.get()
        if doc.exists:
            content_info = doc.to_dict()
            if 'expiration_date' in content_info and content_info['expiration_date'].replace(tzinfo=timezone.utc) > now:
                pass  # Not expired, content_info is valid to use
            else:
                # Handle expired or missing expiration_date
                content_info = {
                    "type": "image",
                    "file": "default.png",
                    "public_url": default_img
                }
        else:
            # Document does not exist
            content_info = {
                "type": "image",
                "file": "default.png",
                "public_url": default_img
            }
    else:
        # Fetch all documents considering expiration_date
        docs = db.collection('events').where('expiration_date', '>', now).stream()
        content_map = {doc.id: doc.to_dict() for doc in docs}
        content_info = list(content_map.values())[0] if content_map else {
            "type": "image",
            "file": "default.png",
            "public_url": default_img
        }

    # Ensure content_map is defined for both cases, adjusting its structure or content as necessary
    return render_template('index.html', content_info=content_info, content_map=content_map)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
