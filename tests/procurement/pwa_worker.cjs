'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../themes/kuranea/assets/sw.js'), 'utf8');
const origin = 'https://ordenowa.test';

function worker(platform = true, shared = new Map()) {
  const listeners = {};
  const notices = [];
  const opened = [];
  let offline = false;
  let responseHeaders = {'Content-Type':'text/css','Cache-Control':'public,max-age=3600'};
  let fetches = 0;
  let storageBlocked = false;
  let claims = 0;
  const caches = {
    async keys() { if(storageBlocked)throw new Error('storage denied');return [...shared.keys()]; },
    async delete(name) { return shared.delete(name); },
    async open(name) {
      if(storageBlocked)throw new Error('storage denied');
      if (!shared.has(name)) shared.set(name, new Map());
      const entries = shared.get(name);
      const key = req => typeof req === 'string' ? req : req.url;
      return {
        async match(req) { return entries.get(key(req))?.clone(); },
        async put(req, response) { entries.set(key(req), response.clone()); },
        async keys() { return [...entries.keys()].map(url => ({url})); },
        async delete(req) { return entries.delete(key(req)); },
      };
    },
  };
  const self = {
    location: {origin,href:origin+'/sw.js'+(platform?'?platform=procurement':'')},
    navigator: {language:'ja'},
    registration: {scope:origin+'/',async showNotification(title, options) { notices.push({title,...options}); }},
    skipWaiting:async()=>{},
    clients:{claim:async()=>{++claims;},matchAll:async()=>[],openWindow:async(url)=>{ opened.push(url);return {focus:async()=>{}};}},
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  vm.runInNewContext(source, {self,caches,URL,Response,TextDecoder,TextEncoder,setTimeout,clearTimeout,
    fetch:async()=>{++fetches;if(offline)throw new TypeError('offline');return new Response('public-css',{headers:responseHeaders});}});
  return {
    shared, notices, opened, get fetches(){return fetches;},get claims(){return claims;},
    blockStorage(value){storageBlocked=value;},
    setOffline(value) { offline=value; },setHeaders(value) {responseHeaders=value;},
    async event(name, data={}) {
      const pending=[];let response;
      listeners[name]({...data,waitUntil(p){pending.push(p);},respondWith(p){response=Promise.resolve(p);}});
      const result=response?await response:null;
      await Promise.all(pending);
      return result;
    },
    async request(url, options={}) {
      return this.event('fetch',{clientId:'client-A',request:{url:new URL(url,origin).href,method:'GET',mode:'same-origin',destination:'style',
        headers:new Headers(),...options}});
    },
  };
}

(async()=>{
  const app=worker();
  const asset='/themes/kuranea/assets/css/custom.css';
  const first=await app.request(asset);
  assert.ok(first,'Procurement public static asset must be intercepted');
  assert.equal(await first.text(),'public-css');
  app.setOffline(true);
  assert.equal(await (await app.request(asset)).text(),'public-css','Public asset remains available offline');
  assert.equal(app.fetches,2,'Network response updates cache before offline fallback');
  const before=[...app.shared.values()].reduce((sum,entries)=>sum+entries.size,0);
  for(const url of ['/module/ordenowaprocurement/workspace','/index.php?fc=module&module=ordenowaprocurement&controller=workspace&view=points',
    '/ja/my-account','/ja/requests/7','/ja/points','/themes/kuranea/assets/css/custom.css?token=private',
    '/modules/private/attachment.css','https://external.invalid/themes/kuranea/assets/css/custom.css']){
    assert.equal(await app.request(url,{mode:url.includes('custom.css')?'same-origin':'navigate'}),null,'Private or unapproved route bypasses worker: '+url);
  }
  assert.equal(await app.request(asset,{method:'POST'}),null,'POST never intercepted');
  assert.equal(await app.request(asset,{headers:new Headers({Authorization:'Bearer sentinel'})}),null,'Authorization never cached');
  assert.equal(await app.request(asset,{headers:new Headers({Range:'bytes=0-10'})}),null,'Partial responses never cached');
  assert.equal([...app.shared.values()].reduce((sum,entries)=>sum+entries.size,0),before,'Private accesses create no cache entries');
  const noCache=worker();
  for(const headers of [
    {'Content-Type':'text/css','Cache-Control':'private,no-store'},
    {'Content-Type':'text/html','Cache-Control':'public,max-age=3600'},
    {'Content-Type':'text/css','Vary':'Cookie'},
  ]){
    noCache.setHeaders(headers);await noCache.request(asset);
    assert.equal([...noCache.shared.values()].reduce((sum,entries)=>sum+entries.size,0),0,'Sensitive/non-static response rejected');
  }
  const legacy=worker(false);
  assert.equal(await legacy.request(asset),null,'Legacy mode stays cacheless');
  legacy.setOffline(true);
  const fallback=await legacy.request('/',{mode:'navigate',destination:'document'});
  assert.equal(fallback.status,503);assert.equal(fallback.headers.get('Cache-Control'),'no-store');
  assert.match(await fallback.text(),/インターネットに接続できません/);
  const caches=app.shared;
  caches.set('ordenowa-public-static-obsolete',new Map([['old','stale']]));
  caches.set('another-module-cache',new Map());
  await app.event('activate');
  assert.equal(caches.has('ordenowa-public-static-obsolete'),false,'Activation removes own old public asset version');
  assert.equal(caches.has('another-module-cache'),true,'Activation preserves unrelated caches');
  const blocked=worker();blocked.blockStorage(true);
  await blocked.event('activate');
  assert.equal(blocked.claims,1,'Storage denial does not prevent worker activation');
  assert.equal(await (await blocked.request(asset)).text(),'public-css','Storage denial preserves online static response');
  for(const event of ['procurement','points']){
    for(const locale of ['ja','en','ko']){
      const bytes=Buffer.from(JSON.stringify({event,locale}));
      await app.event('push',{data:{arrayBuffer:()=>Uint8Array.from(bytes).buffer}});
      const notice=app.notices.at(-1);
      assert.equal(notice.title,'ORDENOWA');
      assert.equal(notice.data.route,event==='points'?'procurement-points':'procurement-requests');
      assert.ok(!notice.body.includes('100'),'Generic notification exposes no amount');
      await app.event('notificationclick',{notification:{data:notice.data,close(){}}});
      assert.equal(app.opened.at(-1),origin+'/index.php?fc=module&module=ordenowaprocurement&controller=workspace&view='+(event==='points'?'points':'requests'));
    }
  }
  const notices=app.notices.length;
  const bytes=Buffer.from(JSON.stringify({event:'points',locale:'ja',amount:100,url:'https://evil.invalid'}));
  await app.event('push',{data:{arrayBuffer:()=>Uint8Array.from(bytes).buffer}});
  assert.equal(app.notices.length,notices,'Extra personal payload fields rejected');
  await app.event('notificationclick',{notification:{data:{route:'https://evil.invalid'},close(){}}});
  assert.equal(app.opened.at(-1),origin+'/index.php?controller=my-account','Unknown push target uses fixed account');
  console.log('PASS procurement PWA static cache/privacy/offline/update and localized push targets');
})().catch(error=>{console.error(error);process.exitCode=1;});
