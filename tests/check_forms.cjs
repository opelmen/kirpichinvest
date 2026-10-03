// Execute the actual rendered form handler with network and analytics stubs.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
const code = scripts.find(m => m[1].includes('form[data-lead]'))[1];
async function scenario(valid, response, analyticsThrows = false) {
  const fields = {style:{}}, ok = {style:{},innerHTML:''}, error = {style:{}};
  const button = {disabled:false}; let handler, calls = 0, goals=[];
  const form = {reportValidity:()=>valid, addEventListener:(_,h)=>{handler=h}, querySelector:s=>({'button':button,'.err':error,'.fields':fields,'.ok':ok}[s])};
  const context = {document:{querySelectorAll:()=>[form]}, location:{search:'?utm_source=test',pathname:'/test/'}, sessionStorage:{getItem:()=>'',setItem:()=>{}}, URLSearchParams, FormData:class {append(){} get(){return 'buy'}}, window:{ym:true}, ym: (...args)=>{goals.push(args); if(analyticsThrows)throw Error('analytics blocked')}, fetch:async()=>{calls++;if(response instanceof Error)throw response;return response}};
  vm.runInNewContext(code, context);handler({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  return {calls,goals,button,fields,ok,error};
}
(async()=>{
  let r=await scenario(false,{ok:true,json:async()=>({ok:true})});assert.equal(r.calls,0);
  r=await scenario(true,{ok:true,json:async()=>({ok:true})});assert.equal(r.goals.length,1);assert.equal(r.goals[0][2],'lead_buy');assert.equal(r.ok.style.display,'block');
  r=await scenario(true,{ok:true,json:async()=>({ok:false,error:'validation'})});assert.equal(r.goals.length,0);assert.equal(r.button.disabled,false);assert.equal(r.error.textContent,'validation');
  r=await scenario(true,{ok:false,status:500,json:async()=>({ok:true})});assert.equal(r.goals.length,0);assert.equal(r.button.disabled,false);
  r=await scenario(true,new Error('offline'));assert.equal(r.goals.length,0);assert.equal(r.button.disabled,false);
  r=await scenario(true,{ok:true,json:async()=>({ok:true})},true);assert.equal(r.ok.style.display,'block');assert.equal(r.error.style.display,'none');
  console.log('PASS: 6 form cases; no real requests or leads sent');
})().catch(e=>{console.error(e);process.exit(1)});
