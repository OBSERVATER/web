import os
from flask import Flask, render_template, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run-script', methods=['POST'])
def run_script():
    # 获取请求数据（如果有）
    data = request.json
    account = data.get('account',0)
    password = data.get('password',0)
    # 调用外部Python脚本
    result = subprocess.run(['python', 'py/main.py',str(account),str(password)], capture_output=True, text=True)
    # 返回脚本输出
    return jsonify({'output': "输出:"+result.stdout})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
