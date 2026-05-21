#!/usr/bin/env python3
import sqlite3
import os
import logging
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
app.debug = False

logging.basicConfig(level=logging.INFO)
DATABASE = '/home/ec2-user/app/users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

HTML_SECURE = '''
<!DOCTYPE html>
<html>
<head><title>AcmeCorp Portal — Secure</title>
<style>body{font-family:Arial;max-width:800px;margin:50px auto;padding:20px;}
.secure{background:#d4edda;border:1px solid #28a745;padding:10px;margin:10px 0;}
table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ddd;padding:8px;}</style>
</head>
<body>
<h1>AcmeCorp Employee Portal — Secure Version</h1>
<div class="secure">SQL injection has been fixed. Parameterized queries in use.</div>
<h2>Employee Search</h2>
<form action="/search" method="GET">
<input type="text" name="username" placeholder="Enter username" value="{{ search_term }}">
<button type="submit">Search</button>
</form>
{% if results is not none %}
<h3>Results</h3>
{% if results %}
<table><tr><th>Username</th><th>Email</th></tr>
{% for row in results %}<tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>{% endfor %}
</table>
{% else %}<p>No results found.</p>{% endif %}
{% endif %}
</body></html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_SECURE, search_term='', results=None)

@app.route('/search')
def search():
    username = request.args.get('username', '').strip()
    conn = get_db()
    cursor = conn.cursor()
    # PARAMETERIZED QUERY — the ? placeholder prevents SQL injection
    # The input is treated as data, never as SQL syntax
    cursor.execute("SELECT username, email FROM users WHERE username = ?", (username,))
    results = cursor.fetchall()
    conn.close()
    logging.info("Search query executed")
    return render_template_string(HTML_SECURE, search_term=username, results=results)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
