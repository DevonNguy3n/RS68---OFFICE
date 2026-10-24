import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, RoundedBox, Text } from '@react-three/drei';

const cyan = '#00bfff';
function Box({position,args,color='#143451',emissive,opacity=1,metalness=.35}) {
  return <mesh position={position} castShadow receiveShadow><boxGeometry args={args}/><meshStandardMaterial color={color} emissive={emissive||'#000000'} emissiveIntensity={emissive?.55:0} metalness={metalness} roughness={.32} transparent={opacity<1} opacity={opacity}/></mesh>;
}
function LightStrip({position,args}) { return <Box position={position} args={args} color="#038ade" emissive="#06b8ff"/> }
function Screen({position,rotation=[0,0,0],width=.8,height=.48}) {
  return <group position={position} rotation={rotation}><Box position={[0,0,0]} args={[width+.08,height+.08,.07]} color="#071326"/><Box position={[0,0,.046]} args={[width,height,.012]} color="#075389" emissive="#02aaff"/>
    <Box position={[-width*.18,height*.1,.055]} args={[width*.22,.025,.015]} color="#8ceaff" emissive="#24d7ff"/><Box position={[0,-height*.13,.055]} args={[width*.62,.025,.015]} color="#3e91c4"/></group>;
}
function Avatar({active}) { return <group><mesh position={[0,1.38,.78]}><sphereGeometry args={[.19,20,20]}/><meshStandardMaterial color={active?'#70ffff':'#c9efff'} emissive="#1179cb" emissiveIntensity={.4}/></mesh><mesh position={[0,.96,.78]}><capsuleGeometry args={[.19,.45,4,12]}/><meshStandardMaterial color="#0b5388"/></mesh></group> }
function Workstation({agent,position,active,onSelect}) { return <group position={position} onClick={e=>{e.stopPropagation();onSelect(agent)}}>
  <Box position={[0,.72,0]} args={[2.4,.13,1.05]} color="#59758e" metalness={.6}/>
  {[-1,1].map((x,i)=><Box key={i} position={[x,.35,0]} args={[.1,.65,.08]} color="#172b42"/>)}
  <LightStrip position={[0,.64,.52]} args={[2.2,.025,.025]}/>
  <Screen position={[-.43,1.16,-.28]}/><Screen position={[.43,1.16,-.28]}/>
  <Box position={[0,.38,.88]} args={[.55,.13,.45]} color="#071b31"/><Box position={[0,.75,1.04]} args={[.56,.62,.1]} color="#0a2442"/>
  <Avatar active={active}/><Html center position={[0,1.98,.4]} distanceFactor={13}><button className={'agent-label '+(active?'active':'')} onClick={()=>onSelect(agent)}>{agent.name}</button></Html>
  </group> }
function Plant({position}) { return <group position={position}><mesh position={[0,.19,0]}><cylinderGeometry args={[.2,.15,.4,8]}/><meshStandardMaterial color="#33495d"/></mesh>{[[.1,.57,0],[-.16,.5,.1],[0,.64,-.1]].map((p,i)=><mesh key={i} position={p} rotation={[.2,i*1.5,.5]}><coneGeometry args={[.25,.65,5]}/><meshStandardMaterial color="#08795e"/></mesh>)}</group> }
function Room() { return <group>
  <Box position={[0,-.1,0]} args={[19,.2,13]} color="#0a1c34" metalness={.65}/>
  <gridHelper args={[19,19,'#0b5384','#14304b']} position={[0,.015,0]}/>
  <Box position={[0,1.2,-6.5]} args={[19,2.5,.12]} color="#102d50" opacity={.75}/><Box position={[-9.5,1.1,0]} args={[.12,2.3,13]} color="#183955" opacity={.6}/>
  <Box position={[9.5,1.1,0]} args={[.12,2.3,13]} color="#183955" opacity={.6}/>
  <Box position={[0,.7,6.5]} args={[19,1.4,.09]} color="#0c2a4a" opacity={.65}/>
  <LightStrip position={[0,.06,-6.35]} args={[18.8,.045,.045]}/><LightStrip position={[0,2.47,-6.38]} args={[18.8,.05,.05]}/>
  <LightStrip position={[-9.36,.06,0]} args={[.05,.05,12.7]}/><LightStrip position={[9.36,.06,0]} args={[.05,.05,12.7]}/>
  <LightStrip position={[0,.5,6.42]} args={[18.8,.05,.05]}/>
  {[-8.5,8.5].map((x,i)=><Plant key={i} position={[x,0,-5.5]}/>)}
  </group> }
function WallDashboard() { return <group>
  {[-5.4,-1.85,1.7,5.25].map((x,i)=><group key={i}><Box position={[x,1.46,-6.34]} args={[3.2,1.35,.08]} color="#052a57" emissive="#063c6b"/><LightStrip position={[x,2.14,-6.28]} args={[3.15,.025,.025]}/><Text position={[x,1.98,-6.27]} fontSize={.17} color="#e5f8ff">{['BẢNG TIẾN ĐỘ DỰ ÁN','HIỆU SUẤT NỘI DUNG','TRẠNG THÁI TASK','NỘI DUNG NỔI BẬT'][i]}</Text></group>)}
  <mesh position={[-5.4,1.36,-6.27]} rotation={[0,0,-Math.PI/2]}><torusGeometry args={[.36,.075,8,40,Math.PI*1.5]}/><meshBasicMaterial color={cyan}/></mesh>
  {[.2,.35,.48,.61,.78].map((h,i)=><Box key={i} position={[-2.65+i*.36,1.1+h/2,-6.25]} args={[.22,h,.025]} color="#048ceb" emissive="#08a9ff"/>)}
  {[1.35,1.05,.75].map((y,i)=><LightStrip key={i} position={[1.7,y,-6.25]} args={[2.3,.025,.025]}/>)}
  {[1.35,1.05,.75].map((y,i)=><Box key={i} position={[4.6,y,-6.25]} args={[1.1,.13,.025]} color="#087fc4" emissive="#027dcb"/>)}
  </group> }
function MeetingRoom(){return <group><Box position={[6.5,.7,.7]} args={[.09,1.4,8]} color="#31638e" opacity={.3}/><LightStrip position={[6.52,1.4,.7]} args={[.04,.03,8]}/><Box position={[7.85,.74,-1]} args={[2.1,.16,3.3]} color="#896a57"/>
  {[-2,-.7,.7].map((z,i)=><React.Fragment key={i}><Box position={[6.95,.46,z]} args={[.43,.8,.43]} color="#091d32"/><Box position={[8.8,.46,z]} args={[.43,.8,.43]} color="#091d32"/></React.Fragment>)}
  <Screen position={[8.55,1.8,-5.7]} width={1.4} height={.85}/><Plant position={[8.8,0,2.7]}/></group>}
function DirectorArea({agent,onSelect,active}){return <group position={[-5.7,0,3.8]} onClick={e=>{e.stopPropagation();onSelect(agent)}}>
  <Box position={[0,.7,0]} args={[3.6,.18,1.4]} color="#3b536d"/><LightStrip position={[0,.64,.72]} args={[3.4,.035,.025]}/>
  {[-1.1,-.45,.45,1.1].map((x,i)=><Screen key={i} position={[x,1.2,-.35]} width={.6} height={.4}/>)}
  <Box position={[0,.45,1]} args={[.6,.15,.5]} color="#071a31"/><Box position={[0,1,1.17]} args={[.6,.9,.12]} color="#102744"/><Avatar active={active}/>
  <Html center position={[0,2.05,.4]} distanceFactor={13}><button className={'agent-label '+(active?'active':'')} onClick={()=>onSelect(agent)}>{agent.name}</button></Html>
  </group>}
function Lounge(){return <group><Box position={[-1,.38,4.2]} args={[1.1,.46,2.3]} color="#e0e9f2"/><Box position={[1.3,.38,4.2]} args={[1.1,.46,2.3]} color="#e0e9f2"/><Box position={[.15,.36,4.2]} args={[.65,.15,.8]} color="#21344d"/><Plant position={[2.8,0,4.8]}/></group>}
export default function Office3D({agents,selected,onSelect}){
  const staff=agents.filter(a=>!['director','manager'].includes(a.id));
  const spots=[[-6,0,-2.2],[-3.4,0,-2.2],[-6,0,.6],[-3.4,0,.6]];
  return <Canvas shadows dpr={[1,1.6]} camera={{position:[13,10,15],fov:44,near:.1,far:100}}>
    <color attach="background" args={['#020b1b']}/><ambientLight intensity={1.6}/><directionalLight position={[4,12,8]} intensity={3} castShadow/><pointLight position={[-4,5,0]} intensity={90} color="#06a8ff"/><pointLight position={[7,4,-2]} intensity={55} color="#4eaeff"/>
    <Room/><WallDashboard/><MeetingRoom/><Lounge/>
    {staff.map((a,i)=><Workstation key={a.id} agent={a} position={spots[i]} active={selected?.id===a.id} onSelect={onSelect}/>)}
    {agents.find(a=>a.id==='director')&&<DirectorArea agent={agents.find(a=>a.id==='director')} onSelect={onSelect} active={selected?.id==='director'}/>}
    {agents.find(a=>a.id==='manager')&&<Workstation agent={agents.find(a=>a.id==='manager')} position={[3.5,0,1.3]} active={selected?.id==='manager'} onSelect={onSelect}/>}
    <OrbitControls makeDefault target={[0,.5,0]} minDistance={8} maxDistance={35} maxPolarAngle={1.48} enablePan={false}/>
  </Canvas>
}
