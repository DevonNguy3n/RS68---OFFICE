from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import json
import threading
import time
from contextlib import contextmanager
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
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
REVIEW_CHAIN = ('research-lead', 'content-lead', 'manager', 'director')
STATUSES = {'DRAFT', 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'APPROVED', 'COMPLETED', 'BLOCKED'}
TRANSITIONS = {'DRAFT': {'ASSIGNED'}, 'ASSIGNED': {'IN_PROGRESS', 'BLOCKED'}, 'IN_PROGRESS': {'SUBMITTED', 'BLOCKED'}, 'SUBMITTED': {'APPROVED', 'REVISION_REQUIRED'}, 'REVISION_REQUIRED': {'IN_PROGRESS'}, 'APPROVED': {'COMPLETED'}, 'BLOCKED': {'IN_PROGRESS'}}

@contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

def init_db():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, assignee TEXT NOT NULL, brief TEXT NOT NULL, status TEXT NOT NULL DEFAULT "DRAFT", result TEXT NOT NULL DEFAULT "", created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, from_status TEXT, to_status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, note TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, author TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, draft_id INTEGER NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, checklist TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS agent_steps (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, agent_id TEXT NOT NULL, stage TEXT NOT NULL, output TEXT NOT NULL, created_at TEXT NOT NULL)')

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

class SourceCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    url: str = Field(pattern=r'^https?://', max_length=2000)
    note: str = ''
    verified: bool = False

class DraftCreate(BaseModel):
    body: str = Field(min_length=10)
    author: str = 'writer'

class ReviewCreate(BaseModel):
    reviewer: str = 'content-lead'
    decision: str = Field(pattern='^(pass|revise|verify)$')
    checklist: dict[str, bool]
    note: str = ''

class GenerateRequest(BaseModel):
    mode: str = Field(pattern='^(research|draft)$')
    demo: bool = True

class AgentMessage(BaseModel):
    agent_id: str
    message: str = Field(min_length=1, max_length=2000)


def ai_settings():
    provider = os.getenv('AI_PROVIDER', 'openai').lower()
    if provider == 'muse2api':
        return (os.getenv('AI_API_KEY') or os.getenv('MUSE2API_KEY'),
                os.getenv('AI_BASE_URL', 'http://127.0.0.1:18610/v1').rstrip('/'),
                os.getenv('AI_MODEL', 'muse-spark'))
    if provider == 'openai':
        return (os.getenv('AI_API_KEY') or os.getenv('OPENAI_API_KEY'),
                os.getenv('AI_BASE_URL', 'https://api.openai.com/v1').rstrip('/'),
                os.getenv('AI_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-5-mini'))
    raise HTTPException(503, 'Unsupported AI_PROVIDER')


def ai_text(instructions, input_data):
    key, base_url, model = ai_settings()
    if not key:
        raise HTTPException(503, 'AI provider key is not configured')
    payload = {'model': model, 'store': False, 'instructions': instructions, 'input': input_data}
    request = Request(f'{base_url}/responses', data=json.dumps(payload).encode(),
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise HTTPException(502, 'AI provider request failed') from exc
    content = '\n'.join(part.get('text', '') for item in result.get('output', [])
                        for part in item.get('content', []) if part.get('type') == 'output_text').strip()
    if not content:
        raise HTTPException(502, 'AI returned no text')
    return content

@app.get('/api/dashboard')
def dashboard():
    with connect() as db:
        by_status = {row['status']: row['count'] for row in db.execute('SELECT status, COUNT(*) AS count FROM tasks GROUP BY status')}
        by_category = {row['category']: row['count'] for row in db.execute('SELECT category, COUNT(*) AS count FROM tasks GROUP BY category')}
        assigned = {row['assignee']: row['count'] for row in db.execute('SELECT assignee, COUNT(*) AS count FROM tasks GROUP BY assignee')}
        return {
            'total': sum(by_status.values()), 'by_status': by_status, 'by_category': by_category,
            'by_agent': assigned,
            'sources': db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],
            'verified_sources': db.execute('SELECT COUNT(*) FROM sources WHERE verified=1').fetchone()[0],
            'drafts': db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0],
            'reviews': db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],
        }

@app.post('/api/agent-chat')
def agent_chat(data: AgentMessage):
    agent = next((item for item in AGENTS if item['id'] == data.agent_id), None)
    if not agent:
        raise HTTPException(422, 'Unknown agent')
    with connect() as db:
        task_rows = [dict(row) for row in db.execute('SELECT id,title,status,brief FROM tasks WHERE assignee=? ORDER BY id DESC LIMIT 5', (data.agent_id,))]
    key = ai_settings()[0]
    if not key:
        if task_rows:
            latest = task_rows[0]
            reply = f'Tôi đang phụ trách "{latest["title"]}" (trạng thái: {latest["status"]}). Bạn có thể mở hồ sơ task để xem nguồn, bản nháp và QC.'
        else:
            reply = 'Hiện tôi chưa được giao task nào. Hãy giao việc trong Trung tâm điều hành để bắt đầu.'
        return {'agent_id': data.agent_id, 'reply': reply, 'mode': 'local', 'tasks': task_rows}
    reply = ai_text(
        f'Bạn là {agent["name"]} của công ty content AI. Vai trò: {agent["role"]}. Trả lời ngắn bằng tiếng Việt. Chỉ xem dữ liệu task cung cấp là sự thật; không bịa tiến độ, nguồn tin hoặc công việc đã làm. Không tự xuất bản.',
        json.dumps({'user_message': data.message, 'assigned_tasks': task_rows}, ensure_ascii=False))
    return {'agent_id': data.agent_id, 'reply': reply, 'mode': 'ai', 'tasks': task_rows}

@app.get('/api/agent-meeting')
def agent_meeting():
    with connect() as db:
        task = db.execute('SELECT id,title,status,assignee FROM tasks ORDER BY id DESC LIMIT 1').fetchone()
        review_rows = []
        if task:
            draft = db.execute('SELECT id FROM drafts WHERE task_id=? ORDER BY id DESC LIMIT 1', (task['id'],)).fetchone()
            if draft:
                review_rows = [dict(row) for row in db.execute('SELECT reviewer,decision,note FROM reviews WHERE draft_id=? ORDER BY id', (draft['id'],))]
    if not task:
        return {'mode': 'local', 'messages': [{'agent_id': 'director', 'text': 'Chưa có nhiệm vụ. Hãy tạo task để bắt đầu trao đổi.'}]}
    task = dict(task)
    assignee = next((agent for agent in AGENTS if agent['id'] == task['assignee']), AGENTS[-1])
    review_by_role = {row['reviewer']: row for row in review_rows}
    participants = ['director', 'research-lead', 'content-lead', 'manager', assignee['id']]
    key = ai_settings()[0]
    if key:
        instructions = ('Tạo cuộc họp ngắn bằng tiếng Việt giữa phó giám đốc, hai leader, quản lý và người nhận task. '
                                    'Hai leader và quản lý phản biện chéo dựa trên review đã lưu; nếu chưa review thì nói rõ đang chờ, không giả vờ đã duyệt. '
                                    'Không khẳng định công việc chưa được ghi nhận. Chỉ trả JSON array có đúng 5 object, mỗi object gồm agent_id và text. '
                                    f'agent_id theo đúng thứ tự: {", ".join(participants)}.')
        try:
            raw = ai_text(instructions, json.dumps({'task': task, 'reviews': review_rows}, ensure_ascii=False))
            messages = json.loads(raw)
            if not isinstance(messages, list) or len(messages) != 5 or any(
                not isinstance(item, dict) or item.get('agent_id') != participants[i] or not isinstance(item.get('text'), str) or not item['text'].strip()
                for i, item in enumerate(messages)
            ):
                raise ValueError('Invalid meeting response')
            return {'mode': 'ai', 'task_id': task['id'], 'messages': messages}
        except (ValueError, TypeError) as exc:
            raise HTTPException(502, 'AI meeting request failed') from exc
    messages = [{'agent_id': 'director', 'text': f'Task #{task["id"]}: {task["title"]}. Trạng thái: {task["status"]}. Mời các bộ phận đối chiếu kết quả.'}]
    for agent_id, topic in [('research-lead', 'nguồn và dữ kiện'), ('content-lead', 'nội dung và ngôn ngữ'), ('manager', 'tổng hợp phản biện')]:
        review = review_by_role.get(agent_id)
        text = f'Đã review {topic}: {review["decision"]}. {review["note"]}' if review else f'Chưa có review {topic} được lưu cho bản nháp hiện tại.'
        messages.append({'agent_id': agent_id, 'text': text})
    messages.append({'agent_id': assignee['id'], 'text': 'Tôi sẽ cập nhật bản nháp và phản hồi các nhận xét đã lưu trong hồ sơ task.'})
    return {'mode': 'local', 'task_id': task['id'], 'messages': messages}

def task_or_404(db, task_id):
    row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Task not found')
    return row

def record_event(db, task_id, old, new, reason):
    db.execute('INSERT INTO events(task_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?)',
               (task_id, old, new, reason, datetime.now(timezone.utc).isoformat()))

def latest_review(db, task_id):
    return db.execute('SELECT * FROM reviews WHERE task_id=? ORDER BY id DESC LIMIT 1', (task_id,)).fetchone()

@app.get('/api/health')
def health():
    return {'ok': True, 'ai_configured': bool(ai_settings()[0]), 'ai_provider': os.getenv('AI_PROVIDER', 'openai').lower()}

@app.get('/api/tasks/{task_id}/sources')
def sources(task_id: int):
    with connect() as db:
        task_or_404(db, task_id)
        return [dict(row) for row in db.execute('SELECT * FROM sources WHERE task_id=? ORDER BY id DESC', (task_id,))]

@app.post('/api/tasks/{task_id}/sources', status_code=201)
def add_source(task_id: int, data: SourceCreate):
    with connect() as db:
        task_or_404(db, task_id)
        cursor = db.execute('INSERT INTO sources(task_id,title,url,note,verified,created_at) VALUES(?,?,?,?,?,?)',
                            (task_id, data.title, data.url, data.note, int(data.verified), datetime.now(timezone.utc).isoformat()))
        record_event(db, task_id, None, 'SOURCE_ADDED', data.url)
        return dict(db.execute('SELECT * FROM sources WHERE id=?', (cursor.lastrowid,)).fetchone())

@app.get('/api/tasks/{task_id}/drafts')
def drafts(task_id: int):
    with connect() as db:
        task_or_404(db, task_id)
        return [dict(row) for row in db.execute('SELECT * FROM drafts WHERE task_id=? ORDER BY version DESC', (task_id,))]

@app.post('/api/tasks/{task_id}/drafts', status_code=201)
def add_draft(task_id: int, data: DraftCreate):
    if data.author not in {a['id'] for a in AGENTS}:
        raise HTTPException(422, 'Unknown author')
    with connect() as db:
        task_or_404(db, task_id)
        version = db.execute('SELECT COALESCE(MAX(version),0)+1 FROM drafts WHERE task_id=?', (task_id,)).fetchone()[0]
        cursor = db.execute('INSERT INTO drafts(task_id,version,body,author,created_at) VALUES(?,?,?,?,?)',
                            (task_id, version, data.body, data.author, datetime.now(timezone.utc).isoformat()))
        record_event(db, task_id, None, 'DRAFT_ADDED', f'v{version} by {data.author}')
        return dict(db.execute('SELECT * FROM drafts WHERE id=?', (cursor.lastrowid,)).fetchone())

@app.get('/api/tasks/{task_id}/reviews')
def reviews(task_id: int):
    with connect() as db:
        task_or_404(db, task_id)
        return [dict(row) for row in db.execute('SELECT * FROM reviews WHERE task_id=? ORDER BY id DESC', (task_id,))]

@app.post('/api/tasks/{task_id}/reviews', status_code=201)
def add_review(task_id: int, data: ReviewCreate):
    if data.reviewer not in REVIEW_CHAIN:
        raise HTTPException(403, 'Reviewer role required')
    required = {'brief', 'facts', 'originality', 'language'}
    if set(data.checklist) != required:
        raise HTTPException(422, 'Incomplete QC checklist')
    if data.decision == 'pass' and not all(data.checklist.values()):
        raise HTTPException(422, 'All checks must pass')
    if data.decision != 'pass' and not data.note.strip():
        raise HTTPException(422, 'Review note required')
    with connect() as db:
        task = task_or_404(db, task_id)
        if task['status'] != 'SUBMITTED':
            raise HTTPException(409, 'Task must be submitted')
        draft = db.execute('SELECT * FROM drafts WHERE task_id=? ORDER BY id DESC LIMIT 1', (task_id,)).fetchone()
        if not draft:
            raise HTTPException(422, 'Draft required')
        if data.reviewer == draft['author']:
            raise HTTPException(403, 'Author cannot review own draft')
        if db.execute('SELECT 1 FROM reviews WHERE draft_id=? AND reviewer=?', (draft['id'], data.reviewer)).fetchone():
            raise HTTPException(409, 'Reviewer already reviewed this draft')
        cursor = db.execute('INSERT INTO reviews(task_id,draft_id,reviewer,decision,checklist,note,created_at) VALUES(?,?,?,?,?,?,?)',
                            (task_id, draft['id'], data.reviewer, data.decision, json.dumps(data.checklist), data.note, datetime.now(timezone.utc).isoformat()))
        record_event(db, task_id, None, 'QC_REVIEWED', data.decision)
        return dict(db.execute('SELECT * FROM reviews WHERE id=?', (cursor.lastrowid,)).fetchone())

@app.post('/api/tasks/{task_id}/generate')
def generate(task_id: int, data: GenerateRequest):
    with connect() as db:
        task = task_or_404(db, task_id)
        source_rows = [dict(row) for row in db.execute('SELECT title,url,note,verified FROM sources WHERE task_id=?', (task_id,))]
        previous_review = latest_review(db, task_id)
        research_note = db.execute('SELECT output FROM agent_steps WHERE task_id=? AND stage="research" ORDER BY id DESC LIMIT 1', (task_id,)).fetchone()
    if data.mode == 'draft' and task['category'] == 'news' and not any(row['verified'] for row in source_rows):
        raise HTTPException(422, 'Verified source required for news')
    if data.demo:
        content = (f'[BẢN MẪU] {task["title"]}\n\nBrief: {task["brief"]}\n\n'
                   'Đây là nội dung mô phỏng để kiểm tra quy trình. Cần biên tập và xác minh trước khi sử dụng.')
    else:
        instructions = ('Bạn là trợ lý nghiên cứu và viết nội dung Facebook. Với tin tức Mỹ, phân biệt dữ kiện và quan điểm, '
                        'không bịa sự kiện, ngày tháng hay trích dẫn. Chỉ sử dụng nguồn được cung cấp và nêu chỗ cần xác minh. '
                        'Với truyện AI, ghi rõ là hư cấu. Không tự xuất bản nội dung.')
        content = ai_text(instructions,
                   json.dumps({'mode': data.mode, 'category': task['category'], 'title': task['title'],
                                        'brief': task['brief'], 'sources': source_rows,
                                        'research_notes': research_note['output'] if research_note and data.mode == 'draft' else '',
                                        'revision_feedback': previous_review['note'] if previous_review and previous_review['decision'] == 'revise' else ''}, ensure_ascii=False))
    return {'mode': data.mode, 'content': content, 'demo': data.demo}

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
        if data.status == 'SUBMITTED' and not db.execute('SELECT 1 FROM drafts WHERE task_id=?', (task_id,)).fetchone():
            raise HTTPException(422, 'Draft required')
        if data.status in {'APPROVED', 'REVISION_REQUIRED'}:
            review = latest_review(db, task_id)
            expected = 'pass' if data.status == 'APPROVED' else 'revise'
            if not review or review['decision'] != expected:
                raise HTTPException(422, 'Matching independent QC review required')
            newest_draft = db.execute('SELECT id FROM drafts WHERE task_id=? ORDER BY id DESC LIMIT 1', (task_id,)).fetchone()
            if not newest_draft or review['draft_id'] != newest_draft['id']:
                raise HTTPException(422, 'Latest draft needs QC review')
            if data.status == 'APPROVED':
                passed = {item['reviewer'] for item in db.execute(
                    'SELECT reviewer FROM reviews WHERE draft_id=? AND decision="pass"', (newest_draft['id'],))}
                if not set(REVIEW_CHAIN) <= passed:
                    raise HTTPException(422, 'Cross-layer reviews from both leads, manager and director required')
        now = datetime.now(timezone.utc).isoformat()
        db.execute('UPDATE tasks SET status=?, result=? WHERE id=?', (data.status, result, task_id))
        db.execute('INSERT INTO events(task_id,from_status,to_status,reason,created_at) VALUES(?,?,?,?,?)', (task_id, row['status'], data.status, data.reason, now))
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())

@app.get('/api/tasks/{task_id}/events')
def events(task_id: int):
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM events WHERE task_id=? ORDER BY id', (task_id,))]

RUN_LOCK = threading.Lock()

def save_agent_step(task_id: int, agent_id: str, stage: str, output: str):
    with connect() as db:
        db.execute('INSERT INTO agent_steps(task_id,agent_id,stage,output,created_at) VALUES(?,?,?,?,?)',
                   (task_id, agent_id, stage, output, datetime.now(timezone.utc).isoformat()))

@app.get('/api/tasks/{task_id}/agent-steps')
def agent_steps(task_id: int):
    with connect() as db:
        task_or_404(db, task_id)
        return [dict(row) for row in db.execute('SELECT * FROM agent_steps WHERE task_id=? ORDER BY id DESC', (task_id,))]

def ai_review(task, draft, reviewer, previous_reviews, sources):
    instructions = ('Bạn là ' + reviewer['name'] + ' trong quy trình review chéo của RS68. '
                         'Đọc nhận xét của các vai trò trước, nêu rõ điểm đồng ý hoặc phản biện trong note; tự đánh giá độc lập, không tự động tin người trước. '
                         'Đánh giá độc lập bản nháp theo brief và nguồn đã lưu. Với tin tức: không xác nhận sự kiện nếu nguồn không hỗ trợ; '
                         'với truyện AI: kiểm tra nhãn hư cấu. Không truy cập web, không bịa bằng chứng. '
                         'Chỉ trả một JSON object gồm decision (pass hoặc revise), checklist '
                         '(brief, facts, originality, language: boolean), note (lý do ngắn). '
                         'Chỉ pass khi cả bốn tiêu chí chắc chắn đạt. Nếu không chắc chắn, revise và ghi rõ cần kiểm tra.')
    try:
        raw = ai_text(instructions, json.dumps({'task': dict(task), 'draft': dict(draft), 'previous_reviews': previous_reviews, 'sources': sources}, ensure_ascii=False))
        parsed = json.loads(raw)
        checks = parsed['checklist']
        required = {'brief', 'facts', 'originality', 'language'}
        if parsed['decision'] not in {'pass', 'revise'} or set(checks) != required or any(type(value) is not bool for value in checks.values()):
            raise ValueError('Invalid review fields')
        if parsed['decision'] == 'pass' and not all(checks.values()):
            raise ValueError('Inconsistent review')
        note = str(parsed.get('note', '')).strip()
        if parsed['decision'] == 'revise' and not note:
            raise ValueError('Missing revision note')
        return ReviewCreate(reviewer=reviewer['id'], decision=parsed['decision'], checklist=checks, note=note)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, 'AI review failed or returned invalid JSON') from exc

def run_agent_cycle(task_id: int):
    if not ai_settings()[0]:
        raise HTTPException(503, 'AI provider key is not configured')
    if not RUN_LOCK.acquire(blocking=False):
        raise HTTPException(409, 'An agent workflow is already running')
    try:
        with connect() as db:
            task = dict(task_or_404(db, task_id))
            verified = db.execute('SELECT COUNT(*) FROM sources WHERE task_id=? AND verified=1', (task_id,)).fetchone()[0]
            revisions = db.execute('SELECT COUNT(*) FROM reviews WHERE task_id=? AND decision="revise"', (task_id,)).fetchone()[0]
        status = task['status']
        if status not in {'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED'}:
            return {'task_id': task_id, 'status': status, 'action': 'idle'}
        if task['category'] == 'news' and not verified:
            return {'task_id': task_id, 'status': status, 'action': 'waiting_for_verified_source'}
        if status == 'REVISION_REQUIRED':
            if revisions >= 2:
                return {'task_id': task_id, 'status': status, 'action': 'human_review_required'}
            transition(task_id, Transition(status='IN_PROGRESS'))
            status = 'IN_PROGRESS'
        if status == 'ASSIGNED':
            transition(task_id, Transition(status='IN_PROGRESS'))
            status = 'IN_PROGRESS'
        if status == 'IN_PROGRESS':
            research = generate(task_id, GenerateRequest(mode='research', demo=False))['content']
            save_agent_step(task_id, 'researcher', 'research', research)
            draft_text = generate(task_id, GenerateRequest(mode='draft', demo=False))['content']
            draft = add_draft(task_id, DraftCreate(body=draft_text, author='writer'))
            save_agent_step(task_id, 'writer', 'draft', f'Đã lưu bản nháp v{draft["version"]}')
            transition(task_id, Transition(status='SUBMITTED', result=f'Bản nháp v{draft["version"]} chờ QC'))
            return {'task_id': task_id, 'status': 'SUBMITTED', 'action': 'draft_submitted'}
        with connect() as db:
            task = dict(task_or_404(db, task_id))
            draft = db.execute('SELECT * FROM drafts WHERE task_id=? ORDER BY id DESC LIMIT 1', (task_id,)).fetchone()
            if not draft:
                raise HTTPException(422, 'Draft required')
            draft = dict(draft)
            previous_reviews = [dict(row) for row in db.execute('SELECT reviewer,decision,note,checklist FROM reviews WHERE draft_id=? ORDER BY id', (draft['id'],))]
            reviewed = {row['reviewer'] for row in previous_reviews}
            sources = [dict(row) for row in db.execute('SELECT title,url,note,verified FROM sources WHERE task_id=?', (task_id,))]
        for agent_id in REVIEW_CHAIN:
            if agent_id in reviewed:
                continue
            reviewer = next(agent for agent in AGENTS if agent['id'] == agent_id)
            decision = ai_review(task, draft, reviewer, previous_reviews, sources)
            add_review(task_id, decision)
            save_agent_step(task_id, agent_id, 'review', f'{decision.decision}: {decision.note}')
            if previous_reviews:
                save_agent_step(task_id, agent_id, 'review-discussion', f'{reviewer["name"]} phản hồi ý kiến của {previous_reviews[-1]["reviewer"]}: {decision.note}')
            if decision.decision == 'revise':
                transition(task_id, Transition(status='REVISION_REQUIRED', reason=decision.note))
                return {'task_id': task_id, 'status': 'REVISION_REQUIRED', 'action': 'revision_requested', 'reviewer': agent_id}
            return {'task_id': task_id, 'status': 'SUBMITTED', 'action': 'review_passed', 'reviewer': agent_id}
        transition(task_id, Transition(status='APPROVED'))
        save_agent_step(task_id, 'director', 'approval', 'Đã duyệt chéo qua hai leader, quản lý và phó giám đốc; chờ người dùng hoàn thành task.')
        return {'task_id': task_id, 'status': 'APPROVED', 'action': 'approved'}
    finally:
        RUN_LOCK.release()

@app.post('/api/tasks/{task_id}/run')
def run_task_agents(task_id: int):
    return run_agent_cycle(task_id)

def auto_agent_loop():
    retry_after = {}
    while True:
        if ai_settings()[0]:
            row = None
            try:
                with connect() as db:
                    candidates = db.execute('''SELECT t.id FROM tasks t WHERE t.status IN ("ASSIGNED","IN_PROGRESS","SUBMITTED","REVISION_REQUIRED")
                        AND (t.category="story" OR EXISTS (SELECT 1 FROM sources s WHERE s.task_id=t.id AND s.verified=1))
                        AND (t.status!="REVISION_REQUIRED" OR (SELECT COUNT(*) FROM reviews r WHERE r.task_id=t.id AND r.decision="revise")<2)
                        ORDER BY t.id''').fetchall()
                    row = next((item for item in candidates if retry_after.get(item['id'], 0) <= time.monotonic()), None)
                if row:
                    run_agent_cycle(row['id'])
                    retry_after.pop(row['id'], None)
            except (HTTPException, OSError, ValueError) as exc:
                if row:
                    retry_after[row['id']] = time.monotonic() + 300
                    save_agent_step(row['id'], 'system', 'error', str(exc))
        threading.Event().wait(20)

@app.on_event('startup')
def start_agent_loop():
    worker = getattr(app.state, 'agent_worker', None)
    if worker is None or not worker.is_alive():
        app.state.agent_worker = threading.Thread(target=auto_agent_loop, daemon=True, name='rs68-agent-loop')
        app.state.agent_worker.start()
