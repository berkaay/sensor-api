from flask import Flask, request, jsonify
import requests, re
from datetime import datetime

app = Flask(__name__)
API_KEY = "use_env_variable"

@app.route('/summary')
def get_summary():
    return jsonify({"message": "API working. Implement logic here."})