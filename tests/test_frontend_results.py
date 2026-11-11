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
