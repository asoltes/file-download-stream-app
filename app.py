from flask import Flask, render_template, jsonify
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

START_TIME = datetime.utcnow()

def get_uptime():
    delta = datetime.utcnow() - START_TIME
    return str(delta).split('.')[0]  # drop microseconds

POD_NAME = os.getenv("POD_NAME", "unknown-pod")
NODE_NAME = os.getenv("NODE_NAME", "unknown-node")
POD_IP = os.getenv("POD_IP", "unknown-ip")
HOST_IP = os.getenv("HOST_IP", "unknown-host")

# Config
BUCKET_NAME = "andres-stream-download"
REGION_NAME = "ap-southeast-1"
URL_EXPIRY_SECONDS = 300  # 5 minutes

# AWS client
s3_client = boto3.client('s3', region_name=REGION_NAME)


# ==== Enhanced In-Memory Cache ====

class PresignedUrlCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._cache.get(key)
            if item and datetime.utcnow() < item['expires_at']:
                return item
            elif item:
                # Clean up expired
                del self._cache[key]
            return None

    def set(self, key, url, expires_at):
        with self._lock:
            self._cache[key] = {
                'url': url,
                'expires_at': expires_at
            }

    def clear_expired(self):
        with self._lock:
            now = datetime.utcnow()
            expired_keys = [k for k, v in self._cache.items() if now >= v['expires_at']]
            for k in expired_keys:
                del self._cache[k]

    def debug_dump(self):
        with self._lock:
            return {k: {'url': v['url'], 'expires_at': v['expires_at'].isoformat()} for k, v in self._cache.items()}


# Initialize cache
url_cache = PresignedUrlCache()


def generate_or_get_presigned_url(key):
    now = datetime.utcnow()
    cached = url_cache.get(key)

    if cached:
        return cached['url'], cached['expires_at'].isoformat() + 'Z'

    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': key},
            ExpiresIn=URL_EXPIRY_SECONDS
        )
        expires_at = now + timedelta(seconds=URL_EXPIRY_SECONDS)
        url_cache.set(key, presigned_url, expires_at)
        return presigned_url, expires_at.isoformat() + 'Z'
    except ClientError as e:
        print(f"Couldn't generate URL for {key}: {e}")
        return None, None


@app.route('/')
def list_objects():
    try:
        url_cache.clear_expired()
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        contents = response.get('Contents', [])
        files = []

        for obj in contents:
            key = obj['Key']
            url, expires_at = generate_or_get_presigned_url(key)
            if url:
                files.append({'key': key, 'url': url, 'expires_at': expires_at})

        return render_template("index.html", files=files, bucket_name=BUCKET_NAME, pod_name=POD_NAME, node_name=NODE_NAME, pod_ip=POD_IP, host_ip=HOST_IP,  uptime=get_uptime())

    except ClientError as e:
        return f"Error accessing bucket: {str(e)}", 500


@app.route('/api/presigned_url', methods=['GET'])
def get_presigned_urls():
    try:
        url_cache.clear_expired()
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        contents = response.get('Contents', [])
        files = []

        for obj in contents:
            key = obj['Key']
            url, expires_at = generate_or_get_presigned_url(key)
            if url:
                files.append({'key': key, 'url': url, 'expires_at': expires_at})

        return jsonify({'bucket_name': BUCKET_NAME, 'files': files})

    except ClientError as e:
        return jsonify({'error': f"Error accessing bucket: {str(e)}"}), 500


# Optional debug route
@app.route('/debug/cache')
def debug_cache():
    return jsonify(url_cache.debug_dump())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
