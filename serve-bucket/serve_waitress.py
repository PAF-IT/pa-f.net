from waitress import serve
from serve import app

PORT=8080
print(f"SERVING ON PORT {PORT}")
serve(app, host='0.0.0.0', port=PORT)
