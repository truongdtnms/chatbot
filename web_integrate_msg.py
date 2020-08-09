import base64
import time
import os

from flask import Flask, jsonify, request, render_template
app = Flask(__name__)

@app.route('/')
def index():
	time.sleep(10)
	return '<h1>Index Page: '+ str(time.time())+'</h1>'

@app.route('/webdemo', methods=['GET'])
def chamcong():
	return render_template('web_integrate_msg.html')
