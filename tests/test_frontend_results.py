"""Run result-rendering code with DOM doubles; Node is optional for this check."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional; render checks need it")
@pytest.mark.parametrize("page", ["app.js", "monitor.js", "dashboard.js"])
def test_ui_never_calls_absence_of_detections_a_pass(page):
    code = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
const element = () => ({innerHTML:'',textContent:'',style:{},addEventListener(){},
  classList:{add(){},remove(){},toggle(){}}});
const sandbox = {document:{getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element},
  window:{location:{origin:'http://test'}},location:{protocol:'http:',host:'test'},
  WebSocket:class{addEventListener(){}},setInterval(){},setTimeout(){},
  fetch:async()=>({ok:true,json:async()=>({model_loaded:false,inspections:[],buckets:[]})})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
if (process.argv[1].endsWith('dashboard.js')) {
  vm.runInContext(`renderHistory([{status:'NO_DETECTIONS',timestamp:'2026-11-10T00:00:00Z'},
    {status:'PASS',timestamp:'2026-11-10T00:00:00Z'}]);`,sandbox);
  const html=elements.get('historyList').innerHTML;
  assert.ok(html.includes('NO DETECTIONS') && html.includes('LEGACY / UNVERIFIED'));
  assert.ok(!html.includes('>PASS<'));
} else {
  vm.runInContext(`renderResult({status:'NO_DETECTIONS',defects_found:0,defects:[],severity:null,annotated_image:''});`,sandbox);
  let html=elements.get('resultCard').innerHTML;
  assert.ok(html.includes('NO DETECTIONS') && html.includes('unverified'));
  assert.ok(!html.includes('>PASS<'));
  vm.runInContext(`renderResult({status:'FAIL',defects_found:1,defects:[{class_name:'patches',confidence:87.5,severity:'MINOR'}],severity:'MINOR',annotated_image:''});`,sandbox);
  html=elements.get('resultCard').innerHTML;
  assert.ok(html.includes('DEFECTS DETECTED') && html.includes('87.5%'));
}
'''
    subprocess.run(["node", "-e", code, str(ROOT / "frontend" / page)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(shutil.which("node") is None, reason="Optional Node rendering check")
def test_camera_ui_preview_never_records_and_manual_network_retry_reuses_uuid():
    code = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls=new Map(),ticks=[],requests=[],ids=[];
let records=0,loseFirstReply=true;
const current={state:'running',running:true,source_type:'video',source:'demo.avi',requested_device:'cpu',confidence:0.4,
  frames_processed:50,inspections_recorded:0,effective:{width:320,height:240,fps:10},inference_device:'cpu',inference_ms:10};
function element(id=''){
  const item={value:'',textContent:'',hidden:true,options:[],events:{},children:[],
    addEventListener(event,handler){this.events[event]=handler;},
    appendChild(child){this.children.push(child);this.options.push(child);},
    replaceChildren(){this.children=[];this.options=[];},removeAttribute(name){delete this[name];}};
  if(id==='serverCameraSource')item.options=[{value:'demo'}];
  return item;
}
function get(id){if(!controls.has(id))controls.set(id,element(id));return controls.get(id);}
const sandbox={document:{getElementById:get,createElement:()=>element()},
  crypto:{randomUUID:()=> '10197ded-706e-4617-88d5-5a7b26a6b809'},setInterval(fn){ticks.push(fn);},
  async fetch(path,options={}){
    requests.push(path);
    let data;
    if(path==='/runtime')data={cuda_available:false,gpus:[],torch_version:'test',cuda_runtime:null};
    else if(path==='/camera/status')data={...current};
    else if(path==='/camera/settings'){current.confidence=JSON.parse(options.body).conf;data={...current};}
    else if(path==='/camera/stop'){current.running=false;current.state='stopped';data={...current};}
    else if(path==='/camera/capture'){
      const id=JSON.parse(options.body).request_id;ids.push(id);
      if(!records){records=1;current.inspections_recorded=1;}
      if(loseFirstReply){loseFirstReply=false;throw Error('reply lost');}
      data={defects_found:0,duplicate:true,captures:{original_url:'/captures/original.jpg',annotated_url:'/captures/annotated.jpg'}};
    } else throw Error('Unexpected '+path);
    return {ok:true,json:async()=>data};
  }};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),sandbox);
(async()=>{
  await new Promise(setImmediate);
  assert.equal(get('serverCameraDevice').value,'cpu');
  assert.equal(get('serverCameraImage').hidden,false); // Reattach to a session after page reload.
  for(let index=0;index<3;index++)await ticks[0]();
  assert.ok(!requests.includes('/camera/capture')); // Polling/preview must not count pieces.
  get('serverCameraConfidence').value='0.99';
  await get('serverCameraApplyConfidence').events.click();
  assert.equal(current.confidence,0.99);
  assert.equal(get('serverCameraStatus').textContent,'Confianza aplicada: 0.99');
  await get('serverCameraCapture').events.click(); // Simulate a committed capture whose reply was lost.
  await get('serverCameraCapture').events.click(); // Retry, not another inspection.
  assert.equal(records,1);assert.equal(ids.length,2);assert.equal(ids[0],ids[1]);
  assert.ok(get('serverCameraStatus').textContent.includes('calidad no verificada'));
  assert.equal(get('serverCaptureDownloads').children.length,2);
  await get('serverCameraStop').events.click();
  assert.equal(get('serverCameraImage').hidden,true);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run(["node", "-e", code, str(ROOT / "frontend" / "camera.js")], check=True, capture_output=True, text=True)
