from flask import Flask, render_template, jsonify, Response
import firebase_admin, requests, os, json
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
from google.cloud import storage
from google.cloud.exceptions import NotFound

# Load the service account key JSON from the environment variable
service_account_info = json.loads(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
cred = credentials.Certificate(service_account_info)

# Initialize Firebase Admin with the credentials
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)
app.secret_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")

default_img = "Midweek.png"

@app.route('/proxy/<path:url>')
def proxy(url):
    # Decode the URL path
    decoded_url = requests.utils.unquote(url)

    try:
        # Make a request to the actual resource
        response = requests.get(decoded_url, stream=True)

        # Check if the request was successful
        if response.status_code == 200:
            return Response(response.iter_content(chunk_size=10*1024),
                            content_type=response.headers['Content-Type'])
        else:
            return Response(f"Error fetching the resource: {response.status_code}", status=response.status_code)
    except requests.RequestException as e:
        return Response(f"Error fetching the resource: {str(e)}", status=500)
    
@app.route('/proxy/<obj_name>')
def blob_proxy(obj_name):
    try:
        # Initialize the Google Cloud Storage client with your service account
        client = storage.Client()
        bucket = client.bucket('xl-exp-llc.appspot.com')
        blob = bucket.blob(f'ar/{obj_name}')

        # Get the blob's content as a bytes object
        content = blob.download_as_bytes()

        return Response(content, content_type=blob.content_type)
    except NotFound:
        # If the object does not exist, return a 404 Not Found response
        return Response("The requested object does not exist.", status=404)
    except Exception as e:
        # Handle other exceptions, such as permission issues or service account misconfiguration
        return Response(f"An error occurred: {str(e)}", status=500)
    
@app.route('/')
@app.route('/<id>')
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
                    "public_url": f"/proxy/{default_img}"
                }
        else:
            # Document does not exist
            content_info = {
                "type": "image",
                "file": "default.png",
                "public_url": f"/proxy/{default_img}"
            }
    else:
        # Fetch all documents considering expiration_date
        docs = db.collection('events').where('expiration_date', '>', now).stream()
        content_map = {doc.id: doc.to_dict() for doc in docs}
        content_info = list(content_map.values())[0] if content_map else {
            "type": "image",
            "file": "default.png",
            "public_url": f"/proxy/{default_img}"
        }

    # Ensure content_map is defined for both cases, adjusting its structure or content as necessary
    return render_template('index.html', content_info=content_info, content_map=content_map)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
