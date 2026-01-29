from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from functools import wraps
from datetime import datetime
import json
import os
import sqlite3
import uuid
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'garion-kanban-secret-2026')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

DB_PATH = os.environ.get('DB_PATH', '/tmp/kanban.db')

# Auth config
AUTH_USER = os.environ.get('KANBAN_USER', 'melgar')
AUTH_PASS = os.environ.get('KANBAN_PASS', 'swap2026')
API_KEY = os.environ.get('KANBAN_API_KEY', 'garion-api-key-2026')

os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else '.', exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            created_at TEXT,
            updated_at TEXT,
            source TEXT DEFAULT 'app'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key == API_KEY:
            return f(*args, **kwargs)
        auth = request.authorization
        if auth and auth.username == AUTH_USER and auth.password == AUTH_PASS:
            return f(*args, **kwargs)
        return jsonify({'error': 'Unauthorized'}), 401
    return decorated_function

def get_all_tasks():
    conn = get_db()
    tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(t) for t in tasks]

def create_task(title, description='', status='todo', priority='medium', source='app'):
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        'INSERT INTO tasks (id, title, description, status, priority, created_at, updated_at, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (task_id, title, description, status, priority, now, now, source)
    )
    conn.commit()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return dict(task)

def update_task(task_id, **kwargs):
    conn = get_db()
    kwargs['updated_at'] = datetime.now().isoformat()
    sets = ', '.join(f'{k} = ?' for k in kwargs.keys())
    values = list(kwargs.values()) + [task_id]
    conn.execute(f'UPDATE tasks SET {sets} WHERE id = ?', values)
    conn.commit()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return dict(task) if task else None

def delete_task(task_id):
    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧠 Garion Kanban - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #e8e8e8;
        }
        .login-box {
            background: rgba(255,255,255,0.05);
            padding: 2.5rem;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            width: 100%;
            max-width: 400px;
        }
        h1 { text-align: center; margin-bottom: 0.5rem; font-size: 2rem; }
        h1 span { color: #00d9ff; }
        .subtitle { text-align: center; color: #888; margin-bottom: 2rem; }
        .form-group { margin-bottom: 1.25rem; }
        label { display: block; margin-bottom: 0.5rem; color: #888; font-size: 0.9rem; }
        input {
            width: 100%;
            padding: 0.875rem;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 1rem;
        }
        input:focus { outline: none; border-color: #00d9ff; }
        button {
            width: 100%;
            padding: 1rem;
            background: #00d9ff;
            color: #000;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: #00b8d9; }
        .error { color: #ff6b6b; text-align: center; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🧠 Garion <span>Kanban</span></h1>
        <p class="subtitle">Faça login para acessar</p>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Usuário</label>
                <input type="text" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label>Senha</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Entrar</button>
        </form>
    </div>
</body>
</html>
'''

TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧠 Garion Kanban</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e8e8e8;
            padding: 1rem;
        }
        header {
            text-align: center;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .header-row { display: flex; justify-content: space-between; align-items: center; max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        h1 span { color: #00d9ff; }
        .logout-btn { background: rgba(255,255,255,0.1); border: none; color: #888; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
        .logout-btn:hover { background: rgba(255,255,255,0.2); color: #fff; }
        .status-bar { display: flex; justify-content: center; gap: 1rem; margin-bottom: 1rem; font-size: 0.85rem; }
        .status-item { display: flex; align-items: center; gap: 0.5rem; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; }
        .status-dot.connected { background: #00ff88; }
        .status-dot.disconnected { background: #ff4444; }
        .board { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; max-width: 1400px; margin: 0 auto; }
        .column { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 1rem; min-height: 70vh; }
        .column-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 2px solid rgba(255,255,255,0.1); }
        .column-title { font-weight: 600; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; }
        .column-count { background: rgba(255,255,255,0.1); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; }
        .column.todo .column-title { color: #ff6b6b; }
        .column.doing .column-title { color: #ffd93d; }
        .column.done .column-title { color: #6bcb77; }
        .tasks { min-height: 200px; }
        .task { background: rgba(0,0,0,0.3); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; cursor: grab; transition: all 0.2s; border-left: 4px solid #666; }
        .task:hover { transform: translateX(4px); background: rgba(0,0,0,0.4); }
        .task.dragging { opacity: 0.5; cursor: grabbing; }
        .task.priority-high { border-left-color: #ff6b6b; }
        .task.priority-medium { border-left-color: #ffd93d; }
        .task.priority-low { border-left-color: #6bcb77; }
        .task-title { font-weight: 500; margin-bottom: 0.5rem; }
        .task-desc { font-size: 0.85rem; color: #888; margin-bottom: 0.5rem; }
        .task-meta { display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #666; }
        .task-source { background: rgba(0,217,255,0.2); color: #00d9ff; padding: 0.15rem 0.5rem; border-radius: 4px; }
        .task-actions { display: flex; gap: 0.5rem; opacity: 0; transition: opacity 0.2s; }
        .task:hover .task-actions { opacity: 1; }
        .task-btn { background: none; border: none; cursor: pointer; font-size: 0.9rem; padding: 0.25rem; }
        .add-task-btn { width: 100%; padding: 0.75rem; background: rgba(255,255,255,0.05); border: 2px dashed rgba(255,255,255,0.2); border-radius: 8px; color: #888; cursor: pointer; transition: all 0.2s; font-size: 0.9rem; }
        .add-task-btn:hover { border-color: #00d9ff; color: #00d9ff; background: rgba(0,217,255,0.1); }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; z-index: 1000; }
        .modal.active { display: flex; }
        .modal-content { background: #1a1a2e; padding: 2rem; border-radius: 16px; width: 90%; max-width: 500px; border: 1px solid rgba(255,255,255,0.1); }
        .modal h2 { margin-bottom: 1.5rem; color: #00d9ff; }
        .form-group { margin-bottom: 1rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-size: 0.9rem; color: #888; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 0.75rem; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; background: rgba(0,0,0,0.3); color: #fff; font-size: 1rem; }
        .form-group textarea { min-height: 80px; resize: vertical; }
        .form-actions { display: flex; gap: 1rem; margin-top: 1.5rem; }
        .btn { flex: 1; padding: 0.75rem; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; transition: all 0.2s; }
        .btn-primary { background: #00d9ff; color: #000; }
        .btn-primary:hover { background: #00b8d9; }
        .btn-secondary { background: rgba(255,255,255,0.1); color: #fff; }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .drop-zone { background: rgba(0,217,255,0.1); border: 2px dashed #00d9ff; }
        .toast { position: fixed; bottom: 2rem; right: 2rem; background: #00d9ff; color: #000; padding: 1rem 1.5rem; border-radius: 8px; font-weight: 500; transform: translateY(100px); opacity: 0; transition: all 0.3s; }
        .toast.show { transform: translateY(0); opacity: 1; }
        .user-info { color: #888; font-size: 0.85rem; }
        @media (max-width: 900px) { .board { grid-template-columns: 1fr; } .column { min-height: auto; } }
    </style>
</head>
<body>
    <header>
        <div class="header-row">
            <div></div>
            <div>
                <h1>🧠 Garion <span>Kanban</span></h1>
            </div>
            <div>
                <span class="user-info">👤 {{ user }}</span>
                <a href="/logout" class="logout-btn">Sair</a>
            </div>
        </div>
        <div class="status-bar">
            <div class="status-item">
                <span class="status-dot" id="connectionStatus"></span>
                <span id="connectionText">Conectando...</span>
            </div>
            <div class="status-item">
                <span>📊</span>
                <span id="taskCount">0 tasks</span>
            </div>
        </div>
    </header>
    <div class="board">
        <div class="column todo" data-status="todo">
            <div class="column-header">
                <span class="column-title">📋 TODO</span>
                <span class="column-count" id="count-todo">0</span>
            </div>
            <div class="tasks" id="tasks-todo"></div>
            <button class="add-task-btn" onclick="openModal('todo')">+ Nova Task</button>
        </div>
        <div class="column doing" data-status="doing">
            <div class="column-header">
                <span class="column-title">🔄 DOING</span>
                <span class="column-count" id="count-doing">0</span>
            </div>
            <div class="tasks" id="tasks-doing"></div>
            <button class="add-task-btn" onclick="openModal('doing')">+ Nova Task</button>
        </div>
        <div class="column done" data-status="done">
            <div class="column-header">
                <span class="column-title">✅ DONE</span>
                <span class="column-count" id="count-done">0</span>
            </div>
            <div class="tasks" id="tasks-done"></div>
            <button class="add-task-btn" onclick="openModal('done')">+ Nova Task</button>
        </div>
    </div>
    <div class="modal" id="taskModal">
        <div class="modal-content">
            <h2 id="modalTitle">Nova Task</h2>
            <form id="taskForm">
                <input type="hidden" id="taskId">
                <input type="hidden" id="taskStatus" value="todo">
                <div class="form-group">
                    <label>Título</label>
                    <input type="text" id="taskTitle" required placeholder="O que precisa ser feito?">
                </div>
                <div class="form-group">
                    <label>Descrição</label>
                    <textarea id="taskDesc" placeholder="Detalhes (opcional)"></textarea>
                </div>
                <div class="form-group">
                    <label>Prioridade</label>
                    <select id="taskPriority">
                        <option value="low">🟢 Baixa</option>
                        <option value="medium" selected>🟡 Média</option>
                        <option value="high">🔴 Alta</option>
                    </select>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
                    <button type="submit" class="btn btn-primary">Salvar</button>
                </div>
            </form>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        const socket = io();
        let tasks = [];
        socket.on('connect', () => {
            document.getElementById('connectionStatus').classList.add('connected');
            document.getElementById('connectionStatus').classList.remove('disconnected');
            document.getElementById('connectionText').textContent = 'Live 🟢';
            socket.emit('get_tasks');
        });
        socket.on('disconnect', () => {
            document.getElementById('connectionStatus').classList.remove('connected');
            document.getElementById('connectionStatus').classList.add('disconnected');
            document.getElementById('connectionText').textContent = 'Desconectado';
        });
        socket.on('tasks_update', (data) => { tasks = data; renderTasks(); });
        socket.on('task_created', (task) => { tasks.push(task); renderTasks(); showToast('Task "' + task.title + '" criada!'); });
        socket.on('task_updated', (task) => { const idx = tasks.findIndex(t => t.id === task.id); if (idx !== -1) tasks[idx] = task; renderTasks(); });
        socket.on('task_deleted', (taskId) => { tasks = tasks.filter(t => t.id !== taskId); renderTasks(); showToast('Task removida'); });
        function renderTasks() {
            ['todo', 'doing', 'done'].forEach(status => {
                const container = document.getElementById('tasks-' + status);
                const filtered = tasks.filter(t => t.status === status);
                document.getElementById('count-' + status).textContent = filtered.length;
                container.innerHTML = filtered.map(task => '<div class="task priority-' + task.priority + '" draggable="true" data-id="' + task.id + '"><div class="task-title">' + escapeHtml(task.title) + '</div>' + (task.description ? '<div class="task-desc">' + escapeHtml(task.description) + '</div>' : '') + '<div class="task-meta"><span class="task-source">' + (task.source === 'clawdbot' ? '🧠 Garion' : '🖥️ App') + '</span><div class="task-actions"><button class="task-btn" onclick="editTask(\'' + task.id + '\')">✏️</button><button class="task-btn" onclick="deleteTask(\'' + task.id + '\')">🗑️</button></div></div></div>').join('');
            });
            document.getElementById('taskCount').textContent = tasks.length + ' tasks';
            setupDragDrop();
        }
        function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
        function setupDragDrop() {
            document.querySelectorAll('.task').forEach(task => {
                task.addEventListener('dragstart', (e) => { e.target.classList.add('dragging'); e.dataTransfer.setData('text/plain', e.target.dataset.id); });
                task.addEventListener('dragend', (e) => { e.target.classList.remove('dragging'); document.querySelectorAll('.tasks').forEach(c => c.classList.remove('drop-zone')); });
            });
            document.querySelectorAll('.tasks').forEach(container => {
                container.addEventListener('dragover', (e) => { e.preventDefault(); container.classList.add('drop-zone'); });
                container.addEventListener('dragleave', () => { container.classList.remove('drop-zone'); });
                container.addEventListener('drop', (e) => { e.preventDefault(); container.classList.remove('drop-zone'); const taskId = e.dataTransfer.getData('text/plain'); const newStatus = container.parentElement.dataset.status; socket.emit('update_task', { id: taskId, status: newStatus }); });
            });
        }
        function openModal(status = 'todo') { document.getElementById('taskModal').classList.add('active'); document.getElementById('modalTitle').textContent = 'Nova Task'; document.getElementById('taskId').value = ''; document.getElementById('taskStatus').value = status; document.getElementById('taskTitle').value = ''; document.getElementById('taskDesc').value = ''; document.getElementById('taskPriority').value = 'medium'; document.getElementById('taskTitle').focus(); }
        function closeModal() { document.getElementById('taskModal').classList.remove('active'); }
        function editTask(id) { const task = tasks.find(t => t.id === id); if (!task) return; document.getElementById('taskModal').classList.add('active'); document.getElementById('modalTitle').textContent = 'Editar Task'; document.getElementById('taskId').value = task.id; document.getElementById('taskStatus').value = task.status; document.getElementById('taskTitle').value = task.title; document.getElementById('taskDesc').value = task.description || ''; document.getElementById('taskPriority').value = task.priority; }
        function deleteTask(id) { if (confirm('Remover esta task?')) { socket.emit('delete_task', { id }); } }
        document.getElementById('taskForm').addEventListener('submit', (e) => { e.preventDefault(); const id = document.getElementById('taskId').value; const data = { title: document.getElementById('taskTitle').value, description: document.getElementById('taskDesc').value, status: document.getElementById('taskStatus').value, priority: document.getElementById('taskPriority').value }; if (id) { socket.emit('update_task', { id, ...data }); } else { socket.emit('create_task', data); } closeModal(); });
        function showToast(message) { const toast = document.getElementById('toast'); toast.textContent = message; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 3000); }
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
    </script>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == AUTH_USER and request.form['password'] == AUTH_PASS:
            session['logged_in'] = True
            session['user'] = AUTH_USER
            return redirect(url_for('index'))
        else:
            error = 'Usuário ou senha inválidos'
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template_string(TEMPLATE, user=session.get('user', 'Guest'))

# REST API for Clawdbot integration (with API key auth)
@app.route('/api/tasks', methods=['GET'])
@api_auth_required
def api_get_tasks():
    return jsonify(get_all_tasks())

@app.route('/api/tasks', methods=['POST'])
@api_auth_required
def api_create_task():
    data = request.json
    task = create_task(
        title=data.get('title'),
        description=data.get('description', ''),
        status=data.get('status', 'todo'),
        priority=data.get('priority', 'medium'),
        source=data.get('source', 'clawdbot')
    )
    socketio.emit('task_created', task)
    return jsonify(task), 201

@app.route('/api/tasks/<task_id>', methods=['PATCH'])
@api_auth_required
def api_update_task(task_id):
    data = request.json
    task = update_task(task_id, **data)
    if task:
        socketio.emit('task_updated', task)
        return jsonify(task)
    return jsonify({'error': 'Task not found'}), 404

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@api_auth_required
def api_delete_task(task_id):
    delete_task(task_id)
    socketio.emit('task_deleted', task_id)
    return '', 204

# WebSocket events
@socketio.on('get_tasks')
def handle_get_tasks():
    emit('tasks_update', get_all_tasks())

@socketio.on('create_task')
def handle_create_task(data):
    task = create_task(title=data.get('title'), description=data.get('description', ''), status=data.get('status', 'todo'), priority=data.get('priority', 'medium'), source='app')
    emit('task_created', task, broadcast=True)

@socketio.on('update_task')
def handle_update_task(data):
    task_id = data.pop('id')
    task = update_task(task_id, **data)
    if task:
        emit('task_updated', task, broadcast=True)

@socketio.on('delete_task')
def handle_delete_task(data):
    task_id = data.get('id')
    delete_task(task_id)
    emit('task_deleted', task_id, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
