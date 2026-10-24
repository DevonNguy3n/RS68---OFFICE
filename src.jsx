import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, RoundedBox, Text } from '@react-three/drei';
import './style.css';
import './workspace.css';

const fallbackAgents = [
  {id:'director',name:'Phó giám đốc',role:'Điều phối',provider:'ChatGPT'},
  {id:'manager',name:'Quản lý',role:'Quản lý task',provider:'ChatGPT'},
  {id:'research-lead',name:'Leader nghiên cứu',role:'Kiểm chứng dữ liệu',provider:'ChatGPT'},
  {id:'content-lead',name:'Leader nội dung',role:'QC nội dung',provider:'ChatGPT'},
  {id:'researcher',name:'Nhân viên nghiên cứu',role:'Thu thập nguồn',provider:'ChatGPT'},
  {id:'writer',name:'Nhân viên viết',role:'Viết nội dung',provider:'ChatGPT'},
];
const positions = [[-5,0,-2],[-2,0,-2],[2,0,-2],[5,0,-2],[-3,0,2],[3,0,2]];
const statusNames = {DRAFT:'Bản nháp',ASSIGNED:'Đã giao',IN_PROGRESS:'Đang làm',SUBMITTED:'Chờ QC',REVISION_REQUIRED:'Cần sửa',APPROVED:'Đã duyệt',COMPLETED:'Hoàn thành',BLOCKED:'Bị chặn'};
const next = {DRAFT:['ASSIGNED'],ASSIGNED:['IN_PROGRESS','BLOCKED'],IN_PROGRESS:['SUBMITTED','BLOCKED'],SUBMITTED:['APPROVED','REVISION_REQUIRED'],REVISION_REQUIRED:['IN_PROGRESS'],APPROVED:['COMPLETED'],BLOCKED:['IN_PROGRESS']};
const api = async (path, options) => { const response = await fetch('/api'+path, options); if (!response.ok) throw new Error((await response.json()).detail || 'Không kết nối được API'); return response.json(); };

function Desk({position,agent,onSelect,active}) {
  return <group position={position} onClick={(event)=>{event.stopPropagation();onSelect(agent)}}>
    <RoundedBox args={[2.3,.15,1.2]} position={[0,.78,0]} radius={.06}><meshStandardMaterial color="#163553" metalness={.65} roughness={.28}/></RoundedBox>
    {[-.9,.9].map(x=><mesh key={x} position={[x,.38,0]}><boxGeometry args={[.1,.76,.1]}/><meshStandardMaterial color="#13233f"/></mesh>)}
    <mesh position={[0,1.18,-.3]}><boxGeometry args={[.84,.52,.05]}/><meshStandardMaterial color="#071627" emissive="#048bea" emissiveIntensity={.8}/></mesh>
    <mesh position={[0,.55,.72]}><boxGeometry args={[.65,.12,.55]}/><meshStandardMaterial color="#101c32"/></mesh>
    <mesh position={[0,1.05,.65]}><sphereGeometry args={[.21,20,20]}/><meshStandardMaterial color={active?'#54f7ec':'#dceeff'} emissive="#0864aa" emissiveIntensity={.3}/></mesh>
    <Html center position={[0,1.85,0]} distanceFactor={12}><button className={'agent-label '+(active?'active':'')} onClick={()=>onSelect(agent)}>{agent.name}</button></Html>
  </group>
}
function Office({agents,selected,onSelect}) {
  return <Canvas shadows camera={{position:[10,12,14],fov:43}}>
    <color attach="background" args={['#031020']}/><ambientLight intensity={.8}/><directionalLight position={[5,12,6]} intensity={2} castShadow/><pointLight position={[0,5,0]} color="#00b8ff" intensity={35}/>
    <mesh rotation={[-Math.PI/2,0,0]} receiveShadow><planeGeometry args={[19,14]}/><meshStandardMaterial color="#0c1b32" metalness={.5} roughness={.35}/></mesh>
    <gridHelper args={[19,19,'#1062a1','#153257']} position={[0,.02,0]}/>
    <mesh position={[0,.6,-7]}><boxGeometry args={[19,1.2,.18]}/><meshStandardMaterial color="#07182e" emissive="#008cff" emissiveIntensity={.15}/></mesh>
    <mesh position={[-9.5,.6,0]}><boxGeometry args={[.18,1.2,14]}/><meshStandardMaterial color="#07182e"/></mesh>
    <mesh position={[9.5,.6,0]}><boxGeometry args={[.18,1.2,14]}/><meshStandardMaterial color="#07182e"/></mesh>
    <Text position={[0,2,-6.82]} fontSize={.45} color="#5de7ff">RS68 CONTENT AI OFFICE</Text>
    {agents.map((agent,i)=><Desk key={agent.id} position={positions[i]} agent={agent} onSelect={onSelect} active={selected?.id===agent.id}/>)}
    <OrbitControls makeDefault enablePan minDistance={6} maxDistance={30} maxPolarAngle={Math.PI/2.05}/>
  </Canvas>
}
function TaskWorkspace({task,onRefresh}) {
  const [sources,setSources]=useState([]),[drafts,setDrafts]=useState([]),[reviews,setReviews]=useState([]),[events,setEvents]=useState([]);
  const [source,setSource]=useState({title:'',url:'',note:'',verified:false}),[body,setBody]=useState(''),[generated,setGenerated]=useState(''),[demo,setDemo]=useState(true),[note,setNote]=useState(''),[error,setError]=useState('');
  const [checks,setChecks]=useState({brief:false,facts:false,originality:false,language:false});
  const load=()=>Promise.all([api(`/tasks/${task.id}/sources`),api(`/tasks/${task.id}/drafts`),api(`/tasks/${task.id}/reviews`),api(`/tasks/${task.id}/events`)]).then(([s,d,r,e])=>{setSources(s);setDrafts(d);setReviews(r);setEvents(e)}).catch(e=>setError(e.message));
  useEffect(()=>{setBody('');setGenerated('');setError('');load()},[task.id]);
  const submit=async(path,payload,done)=>{try{await api(`/tasks/${task.id}/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});setError('');done?.();load();onRefresh()}catch(e){setError(e.message)}};
  const generate=async(mode)=>{try{const value=await api(`/tasks/${task.id}/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,demo})});setGenerated(value.content);setBody(value.content);setError('')}catch(e){setError(e.message)}};
  return <section className="panel workspace"><h2>Hồ sơ task #{task.id} · {task.title}</h2><p className="muted">Nguồn → bản nháp → QC độc lập → phê duyệt. Chế độ mẫu không gọi API AI.</p>{error&&<p className="error">{error}</p>}
    <div className="workspace-grid"><div><h3>1. Nguồn nghiên cứu</h3><form onSubmit={e=>{e.preventDefault();submit('sources',source,()=>setSource({title:'',url:'',note:'',verified:false}))}}><input placeholder="Tên nguồn" required value={source.title} onChange={e=>setSource({...source,title:e.target.value})}/><input type="url" placeholder="https://..." required value={source.url} onChange={e=>setSource({...source,url:e.target.value})}/><input placeholder="Ghi chú xác minh" value={source.note} onChange={e=>setSource({...source,note:e.target.value})}/><label className="check"><input type="checkbox" checked={source.verified} onChange={e=>setSource({...source,verified:e.target.checked})}/> Đã xác minh nguồn</label><button>Lưu nguồn</button></form>{sources.map(s=><p className="item" key={s.id}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> · {s.verified?'✓ Đã xác minh':'Chưa xác minh'}</p>)}</div>
    <div><h3>2. Sản xuất</h3><label className="check"><input type="checkbox" checked={demo} onChange={e=>setDemo(e.target.checked)}/> Chế độ mẫu</label><div className="actions"><button onClick={()=>generate('research')}>AI nghiên cứu</button><button onClick={()=>generate('draft')}>AI viết nháp</button></div><textarea placeholder="Nội dung bản nháp" value={body} onChange={e=>setBody(e.target.value)}/><button onClick={()=>submit('drafts',{body,author:'writer'},()=>setBody(''))}>Lưu phiên bản</button><p className="muted">{drafts.length} phiên bản · bản mới nhất v{drafts[0]?.version||0}</p>{generated&&<p className="muted">Đã tạo nội dung. Kiểm tra kỹ trước khi lưu.</p>}</div>
    <div><h3>3. Kiểm duyệt</h3>{Object.entries({brief:'Đúng brief',facts:'Dữ kiện đã xác minh',originality:'Không sao chép',language:'Ngôn ngữ đạt'}).map(([key,label])=><label className="check" key={key}><input type="checkbox" checked={checks[key]} onChange={e=>setChecks({...checks,[key]:e.target.checked})}/> {label}</label>)}<input placeholder="Ghi chú QC hoặc lý do trả lại" value={note} onChange={e=>setNote(e.target.value)}/><div className="actions"><button onClick={()=>submit('reviews',{reviewer:'content-lead',decision:'pass',checklist:checks,note})}>QC đạt</button><button onClick={()=>submit('reviews',{reviewer:'content-lead',decision:'revise',checklist:checks,note})}>Yêu cầu sửa</button><button onClick={()=>submit('reviews',{reviewer:'content-lead',decision:'verify',checklist:checks,note})}>Chờ xác minh</button></div><p className="muted">{reviews.length} lần QC · {events.length} sự kiện audit</p></div></div>
  </section>
}
function App(){
  const [agents,setAgents]=useState(fallbackAgents), [tasks,setTasks]=useState([]), [selected,setSelected]=useState(null), [selectedTask,setSelectedTask]=useState(null), [error,setError]=useState(''), [form,setForm]=useState({title:'',category:'news',assignee:'researcher',brief:''}), [reason,setReason]=useState(''), [result,setResult]=useState('');
  const refresh=()=>api('/tasks').then(setTasks).catch(e=>setError(e.message));
  useEffect(()=>{api('/agents').then(setAgents).catch(()=>{});refresh()},[]);
  const create=async(e)=>{e.preventDefault();try{await api('/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(form)});setForm({...form,title:'',brief:''});setError('');refresh()}catch(e){setError(e.message)}};
  const move=async(task,status)=>{try{await api(`/tasks/${task.id}/transition`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,reason,result})});setReason('');setResult('');setError('');refresh()}catch(e){setError(e.message)}};
  const assigned=selected?tasks.filter(t=>t.assignee===selected.id):tasks;
  return <div className="app"><header><div className="brand"><span className="logo">◈</span><div><strong>CONTENT AI COMPANY</strong><small>RS68 · Văn phòng điều hành</small></div></div><div className="metrics"><span>Tổng task <b>{tasks.length}</b></span><span>Đang làm <b>{tasks.filter(t=>t.status==='IN_PROGRESS').length}</b></span><span>Chờ QC <b>{tasks.filter(t=>t.status==='SUBMITTED').length}</b></span><span>Hoàn thành <b>{tasks.filter(t=>t.status==='COMPLETED').length}</b></span></div><div className="owner">● Chủ tịch</div></header>
    <aside className="nav"><h3>ĐIỀU HÀNH</h3><a href="#overview">◉ Tổng quan</a><a href="#tasks">▣ Task</a><a href="#agents">♙ Nhân sự AI</a><p>Tin tức Mỹ · Truyện AI<br/>Facebook · chạy local</p></aside>
    <main id="overview"><section className="scene"><Office agents={agents} selected={selected} onSelect={setSelected}/><div className="hint">Kéo để xoay 360° · Cuộn để zoom · Chọn bàn làm việc</div></section><section className="bottom" id="tasks"><div className="panel"><h2>Tạo nhiệm vụ</h2><form onSubmit={create}><input placeholder="Tên nhiệm vụ" value={form.title} onChange={e=>setForm({...form,title:e.target.value})} required minLength="3"/><div className="row"><select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}><option value="news">Tin tức Mỹ</option><option value="story">Truyện AI</option></select><select value={form.assignee} onChange={e=>setForm({...form,assignee:e.target.value})}>{agents.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></div><textarea placeholder="Brief, nguồn và yêu cầu đầu ra" value={form.brief} onChange={e=>setForm({...form,brief:e.target.value})} required minLength="5"/><button>Tạo task</button></form>{error&&<p className="error">{error}</p>}</div><div className="panel"><h2>{selected?`Task của ${selected.name}`:'Danh sách task'}</h2><div className="task-list">{assigned.length?assigned.map(t=><div className="task" key={t.id}><strong>{t.title}</strong><span className="badge">{statusNames[t.status]}</span><small>{t.category==='news'?'Tin tức Mỹ':'Truyện AI'} · {agents.find(a=>a.id===t.assignee)?.name}</small><p>{t.brief}</p>{t.result&&<p>Kết quả: {t.result}</p>}<div className="actions"><button onClick={()=>setSelectedTask(t)}>Mở hồ sơ</button></div><div className="row"><input placeholder="Lý do nếu trả lại/chặn" value={reason} onChange={e=>setReason(e.target.value)}/><input placeholder="Kết quả khi bàn giao" value={result} onChange={e=>setResult(e.target.value)}/></div><div className="actions">{(next[t.status]||[]).map(s=><button key={s} onClick={()=>move(t,s)}>{statusNames[s]}</button>)}</div></div>):<p className="muted">Chưa có task. Tạo nhiệm vụ đầu tiên để bắt đầu.</p>}</div></div></section>{selectedTask&&<TaskWorkspace task={selectedTask} onRefresh={refresh}/>}</main>
    <aside className="right" id="agents"><div className="panel"><h2>Nhân sự AI</h2>{agents.map(a=><button className={'agent-row '+(selected?.id===a.id?'chosen':'')} key={a.id} onClick={()=>setSelected(a)}><span className="avatar">◉</span><span><strong>{a.name}</strong><small>{a.role} · {a.provider}</small></span><i>●</i></button>)}{selected&&<button className="clear" onClick={()=>setSelected(null)}>Xem toàn bộ</button>}</div><div className="panel note"><h2>{selected?.name||'Văn phòng trực tuyến'}</h2><p>{selected?`${selected.role}. Chọn task bên dưới để giao việc và theo dõi tiến độ.`:'Chọn một nhân viên trong văn phòng để xem nhiệm vụ và tương tác.'}</p></div></aside>
  </div>
}
createRoot(document.getElementById('root')).render(<App/>);
