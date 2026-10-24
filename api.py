from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB = Path(__file__).with_name('office.db')
app = FastAPI(title='RS68 Office API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])
AGENTS = [
    {'id': 'director', 'name': 'Phó giám đốc', 'role': 'Điều phối', 'provider': 'ChatGPT'},
    {'id': 'manager', 'name': 'Quản lý', 'role': 'Quản lý task', 'provider': 'ChatGPT'},
    {'id': 'research-lead', 'name': 'Leader nghiên cứu', 'role': 'Kiểm chứng dữ liệu', 'provider': 'ChatGPT'},
    {'id': 'content-lead', 'name': 'Leader nội dung', 'role': 'QC nội dung', 'provider': 'ChatGPT'},
    {'id': 'researcher', 'name': 'Nhân viên nghiên cứu', 'role': 'Thu thập nguồn', 'provider': 'ChatGPT'},
    {'id': 'writer', 'name': 'Nhân viên viết', 'role': 'Viết nội dung', 'provider': 'ChatGPT'},
]
STATUSES = {'DRAFT', 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'APPROVED', 'COMPLETED', 'BLOCKED'}
TRANSITIONS = {'DRAFT': {'ASSIGNED'}, 'ASSIGNED': {'IN_PROGRESS', 'BLOCKED'}, 'IN_PROGRESS': {'SUBMITTED', 'BLOCKED'}, 'SUBMITTED': {'APPROVED', 'REVISION_REQUIRED'}, 'REVISION_REQUIRED': {'IN_PROGRESS'}, 'APPROVED': {'COMPLETED'}, 'BLOCKED': {'IN_PROGRESS'}}

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, assignee TEXT NOT NULL, brief TEXT NOT NULL, status TEXT NOT NULL DEFAULT "DRAFT", result TEXT NOT NULL DEFAULT "", created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, from_status TEXT, to_status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)')

init_db()

class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(pattern='^(news|story)$')
    assignee: str
    brief: str = Field(min_length=5)

class Transition(BaseModel):
    status: str
    reason: str = ''
    result: str = ''

@app.get('/api/agents')
def agents():
    return AGENTS

@app.get('/api/tasks')
def tasks():
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM tasks ORDER BY id DESC')]

@app.post('/api/tasks', status_code=201)
def create_task(data: TaskCreate):
    if data.assignee not in {a['id'] for a in AGENTS}:
        raise HTTPException(422, 'Unknown assignee')
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cursor = db.execute('INSERT INTO tasks(title,category,assignee,brief,created_at) VALUES(?,?,?,?,?)', (data.title, data.category, data.assignee, data.brief, now))
        db.execute('INSERT INTO events(task_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?)', (cursor.lastrowid, None, 'DRAFT', 'Created', now))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (cursor.lastrowid,)).fetchone())

@app.post('/api/tasks/{task_id}/transition')
def transition(task_id: int, data: Transition):
    with connect() as db:
        row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Task not found')
        if data.status not in STATUSES or data.status not in TRANSITIONS.get(row['status'], set()):
            raise HTTPException(409, 'Invalid transition')
        if data.status in {'REVISION_REQUIRED', 'BLOCKED'} and not data.reason.strip():
            raise HTTPException(422, 'Reason required')
        result = data.result.strip() or row['result']
        if data.status in {'SUBMITTED', 'COMPLETED'} and not result:
            raise HTTPException(422, 'Result required')
        now = datetime.now(timezone.utc).isoformat()
        db.execute('UPDATE tasks SET status=?, result=? WHERE id=?', (data.status, result, task_id))
        db.execute('INSERT INTO events(task_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?)', (task_id, row['status'], data.status, data.reason, now))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())

@app.get('/api/tasks/{task_id}/events')
def events(task_id: int):
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM events WHERE task_id=? ORDER BY id', (task_id,))]
