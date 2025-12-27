import os

# Strange non-AWS bucket compatibility issue... (see: https://github.com/fsspec/s3fs/issues/931)
os.environ['AWS_REQUEST_CHECKSUM_CALCULATION'] = 'when_required'
os.environ['AWS_RESPONSE_CHECKSUM_VALIDATION'] = 'when_required'

import boto3
from flask import Flask, request, jsonify, make_response, abort
import json
import tempfile

import palimpsest


s3client = boto3.client(
    service_name='s3',
    aws_access_key_id=os.environ['UPCLOUD_OBJ_ID'],
    aws_secret_access_key=os.environ['UPCLOUD_OBJ_SECRET'],
    endpoint_url=os.environ['UPCLOUD_OBJ_ENDPOINT']
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




@app.route('/edit')
def edit_simple():
    return open('edit_simple.html')

@app.route('/edit/save_version', methods=['POST'])
def save_version():
    version_info = request.get_json()

    sitemap = version_info.get('sitemap')
    version_name = version_info.get('version_name')

    if not (sitemap and version_name):
        abort(400)
    if ' ' in version_name or '/' in version_name:
        print(f"invalid version name: {version_name}")
        abort(400)

    print("Generating site...")

    # Generate and upload the new version!
    with tempfile.TemporaryDirectory() as tdir:
        ssg = palimpsest.StaticSiteGenerator(sitemap, output_dir=tdir)
        ssg.load_sidebar()
        ssg.generate_site()

        # ok! now copy over the tempdir to /version/{version_name}
        print("Success! Saving to bucket")

        # First save the sitemap metadata
        sm_path = f"/meta/version/{version_name}.json"
        with tempfile.NamedTemporaryFile(suffix=".json", mode='w') as sm:
            json.dump(sitemap, sm, indent=2)
            s3client.upload_file(sm.name, bucket, sm_path)

        for (root, dirs, files) in os.walk(tdir):
            for fname in files:
                if not fname.endswith('.html'):
                    continue

                full_path = os.path.join(root, fname)
                obj_path = os.path.join('version', version_name, full_path.replace(tdir, '').lstrip('/'))

                print("UPLOAD", full_path, "to", obj_path)

                s3client.upload_file(full_path, bucket, obj_path,
                                     ExtraArgs={
                                         'ContentType': 'text/html'
                                     })

    return {"ok": True}



if __name__ == '__main__':
    PORT = 8000

    print(f"Starting bucket server (dev) on port {PORT}")

    app.run(host='0.0.0.0', port=PORT, debug=True)
