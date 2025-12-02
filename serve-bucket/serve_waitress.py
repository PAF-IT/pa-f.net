from waitress import serve
from serve import app
import os

PORT=int(os.environ.get('PORT', 8080))

print(f"SERVING ON PORT {PORT}")
serve(app, host='0.0.0.0', port=PORT)
