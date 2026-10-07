from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import os
import socket
import time
import json
import secrets

# 初始化 Flask 应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('EXPERIMENT_SECRET') or secrets.token_hex(32)
# 允许跨域
socketio = SocketIO(app, async_mode='threading')

# 内存变量：存储平板数据以便导出
tablet_data_store = []


# ================= 1. 路由配置 =================
@app.route('/')
def index():
    return """
    <h1>实验服务器已启动</h1>
    <ul>
        <li><a href='/operator'>主试端 (Operator)</a></li>
        <li><a href='/subject'>驾驶模拟端 (Subject)</a></li>
        <li><a href='/tablet'>平板任务端 (NDRT Tablet)</a></li>
    </ul>
    """


@app.route('/operator')
def operator():
    return render_template('operator.html')


@app.route('/subject')
def subject():
    return render_template('subject.html')


@app.route('/tablet')
def tablet():
    return render_template('tablet.html')


# ================= 2. 视频文件服务 =================
@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory('videos', filename)


# ================= 3. WebSocket 通信逻辑 (ErgoLAB 已移除) =================

# --- 通用指令转发 ---
@socketio.on('command')
def handle_command(data):
    action = data.get('action')

    # 如果是同步设置，清空旧数据
    if action == 'syncSettings':
        global tablet_data_store
        tablet_data_store = []  # 重置平板数据
        # 下方统一广播，让各端知道当前 SubjectID。

    # 广播给所有端 (包括 Subject, Tablet)
    emit('cmd_from_server', data, broadcast=True)


# --- 被试端状态 ---
@socketio.on('status')
def handle_status(data):
    # 直接转发状态给 Operator，不再处理 SyncMark
    emit('status_from_subject', data, broadcast=True)


# --- 平板端事件处理 ---
@socketio.on('tablet_event')
def handle_tablet_event(data):
    # 1. 存入内存 (用于导出 CSV)
    tablet_data_store.append(data)

    # 2. 构造日志消息并发送给主试端 (用于时间轴显示)
    evt_type = data.get('type')
    log_msg = ""

    if evt_type == 'click':
        res = data.get('result')
        log_msg = f"Tablet_{res.capitalize()}"  # Tablet_Correct 或 Tablet_Wrong

    elif evt_type == 'reset':
        log_msg = "Tablet_Reset"

    elif evt_type == 'connected':
        log_msg = "Tablet_Connected"

    # 转发给主试端进行 UI 更新
    emit('status_from_tablet', {
        'event': log_msg,
        'raw_data': data
    }, broadcast=True)


# --- 数据导出 ---
@socketio.on('upload_data')
def handle_data(data):
    emit('data_ready_download', data, broadcast=True)


# [导出平板数据]
@socketio.on('request_tablet_data')
def export_tablet_data():
    if not tablet_data_store:
        # 提示主试端无数据
        emit('status_from_subject', {'type': 'toast', 'msg': "当前没有平板数据可导出", 'level': 'error'}, broadcast=True)
        return

    # 生成 CSV
    csv_content = "Timestamp,SubjectID,EventType,Result,CurrentScore,ReactionTime\n"
    for item in tablet_data_store:
        ts = item.get('timestamp', '')
        sid = item.get('subjectId', '')
        etype = item.get('type', '')
        res = item.get('result', '')
        score = item.get('score', '')
        rt = item.get('rt', '')  # 反应时间

        csv_content += f"{ts},{sid},{etype},{res},{score},{rt}\n"

    emit('data_ready_download', {
        'content': csv_content,
        'filename': 'Tablet_Data.csv'
    }, broadcast=True)


# ================= 4. IP 辅助 =================
def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


if __name__ == '__main__':
    host_ip = get_host_ip()
    print(f"\n >>> 主试端: http://localhost:18767/operator")
    print(f" >>> 平板端: http://localhost:18767/tablet")
    print(f" >>> 被试端: http://localhost:18767/subject \n")

    try:
        socketio.run(app, host='127.0.0.1', port=18767, debug=False, allow_unsafe_werkzeug=True)
    except TypeError:
        socketio.run(app, host='127.0.0.1', port=18767, debug=False)