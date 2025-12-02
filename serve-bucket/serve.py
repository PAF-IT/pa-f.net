import os

import boto3
from flask import Flask, request, jsonify, make_response

s3client = boto3.client(
    service_name='s3',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    endpoint_url=os.environ['ENDPOINT_URL']
)
bucket = os.environ['BUCKET_NAME']

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if '.' not in path.split('/')[-1]:
        path = os.path.join(path, 'index.html')

    path = path.strip('/')
    response = s3client.get_object(Key=path, Bucket=bucket)

    def generate():
        for chunk in response['Body'].iter_chunks(chunk_size=1024):
            yield chunk

    content_type = response['ResponseMetadata']['HTTPHeaders'].get('content-type', 'text/html')

    return generate(), {"Content-Type": content_type}


if __name__ == '__main__':
    PORT = 8000

    print(f"Starting bucket server (dev) on port {PORT}")

    app.run(host='0.0.0.0', port=PORT, debug=True)
