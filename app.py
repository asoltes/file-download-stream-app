from flask import Flask, render_template
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

BUCKET_NAME = "andres-stream-download"
REGION_NAME = "ap-southeast-1"
URL_EXPIRY_SECONDS = 300  # 1 hour
# URL_EXPIRY_SECONDS = 3600  # 1 hour

s3_client = boto3.client('s3', region_name=REGION_NAME)

# In-memory URL cache
url_cache = {}
cache_lock = threading.Lock()


@app.route('/')
def list_objects():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        contents = response.get('Contents', [])
        files = []

        with cache_lock:
            for obj in contents:
                key = obj['Key']
                now = datetime.utcnow()

                if key in url_cache:
                    cached = url_cache[key]
                    if now < cached['expires_at']:
                        # Reuse existing URL
                        files.append({
                            'key': key,
                            'url': cached['url'],
                            'expires_at': cached['expires_at'].isoformat() + 'Z'
                        })
                        continue

                # Create new presigned URL and cache it
                try:
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': BUCKET_NAME, 'Key': key},
                        ExpiresIn=URL_EXPIRY_SECONDS
                    )
                    expires_at = now + timedelta(seconds=URL_EXPIRY_SECONDS)

                    url_cache[key] = {
                        'url': presigned_url,
                        'expires_at': expires_at
                    }

                    files.append({
                        'key': key,
                        'url': presigned_url,
                        'expires_at': expires_at.isoformat() + 'Z'
                    })
                except ClientError as e:
                    print(f"Couldn't generate URL for {key}: {e}")
                    continue

        return render_template("index.html", files=files, bucket_name=BUCKET_NAME)

    except ClientError as e:
        return f"Error accessing bucket: {str(e)}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
