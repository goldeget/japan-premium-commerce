'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../themes/kuranea/assets/js/pwa-register.js'),'utf8');
function page({platform=true,ios=false,standalone=false,lang='en',foreign=false}={}){
  const events={};const registered=[];const all=[];
  function element(tag){const node={tagName:tag,children:[],listeners:{},hidden:false,disabled:false,textContent:'',style:{},
    appendChild(child){this.children.push(child);return child;},append(...children){this.children.push(...children);},
    setAttribute(name,value){this[name]=value;},addEventListener(name,callback){this.listeners[name]=callback;}};all.push(node);return node;}
  const body=element('body');
  const document={currentScript:{dataset:{serviceWorker:foreign?'https://evil.invalid/sw.js':'/sw.js',scope:'/'}},baseURI:'https://ordenowa.test/',
    documentElement:{lang},body,createElement:element,
    querySelector(selector){return platform&&selector.includes('ordenowa-platform')?{content:'procurement',getAttribute:()=> 'procurement'}:null;}};
  const navigator={userAgent:ios?'Mozilla/5.0 (iPhone) AppleWebKit/605.1.15':'Mozilla/5.0 Android Chrome/130',platform:ios?'iPhone':'Linux',
    maxTouchPoints:ios?5:0,standalone,serviceWorker:{async register(url,options){registered.push({url,...options});return {};}}};
  const window={location:{origin:'https://ordenowa.test'},matchMedia:()=>({matches:standalone}),
    addEventListener(name,callback){events[name]=callback;}};
  vm.runInNewContext(source,{window,document,navigator,URL});
  return {all,body,events,registered,async trigger(name,event={}){if(events[name])await events[name](event);}};
}
(async()=>{
  const app=page();await app.trigger('load');
  assert.equal(app.registered[0].url,'https://ordenowa.test/sw.js?platform=procurement','Explicit platform marker enables static cache');
  assert.equal(app.registered[0].scope,'/');
  const guide=app.all.find(node=>node['data-ordenowa-install']!==undefined);
  assert.ok(guide,'Procurement install instructions are present');
  const button=app.all.find(node=>node.tagName==='button');assert.ok(button.hidden,'No unavailable native install prompt');
  let prompts=0;let prevented=false;
  await app.trigger('beforeinstallprompt',{preventDefault(){prevented=true;},async prompt(){++prompts;},userChoice:Promise.resolve({outcome:'accepted'})});
  assert.equal(prompts,0,'Install is never prompted automatically');assert.equal(prevented,true);assert.equal(button.hidden,false);
  await button.listeners.click();assert.equal(prompts,1,'Native prompt runs after explicit click');
  await app.trigger('appinstalled');assert.equal(guide.hidden,true,'Installed app removes guidance');
  const ios=page({ios:true,lang:'ja'});await ios.trigger('load');
  assert.ok(ios.all.some(node=>node.textContent.includes('ホーム画面に追加')),'iOS has native Japanese Share/Add to Home Screen instructions');
  const ko=page({ios:true,lang:'ko'});await ko.trigger('load');
  assert.ok(ko.all.some(node=>node.textContent.includes('홈 화면에 추가')),'Korean install guide');
  const standalone=page({standalone:true});await standalone.trigger('load');
  assert.equal(standalone.body.children.length,0,'Installed standalone app has no install guide');
  const legacy=page({platform:false});await legacy.trigger('load');
  assert.equal(legacy.registered[0].url,'https://ordenowa.test/sw.js','Legacy worker stays explicit cacheless mode');
  assert.equal(legacy.body.children.length,0,'Legacy page gains no platform controls');
  const foreign=page({foreign:true});await foreign.trigger('load');assert.equal(foreign.registered.length,0,'Cross-origin worker rejected');
  console.log('PASS procurement PWA explicit registration and user-initiated Android/iOS install guidance');
})().catch(error=>{console.error(error);process.exitCode=1;});
