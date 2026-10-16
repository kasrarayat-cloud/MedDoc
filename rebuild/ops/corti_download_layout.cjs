/* Render actual downloaded Word files with QuillMD's existing local renderer.
 * Approximate HTML layout only; this is not Microsoft Word pagination proof.
 */
'use strict';
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert/strict');
const {chromium}=require('playwright');
const [downloads,out]=process.argv.slice(2),base=path.resolve(__dirname,'..');
if(!downloads||!out||![downloads,out].every(path.isAbsolute))throw Error('Absolute downloads and fresh output directory required.');
fs.mkdirSync(out,{mode:0o700});
const token='c'.repeat(48),assets={};
for(const name of ['docx-frame.js','docx-frame.css','template-preparation.js','template-review.js','vendor/docx-preview/jszip.min.js','vendor/docx-preview/docx-preview.min.js'])assets['/static/'+name]=fs.readFileSync(path.join(base,'static',name));
const frame=fs.readFileSync(path.join(base,'templates/docx_preview_frame.html'),'utf8').replace('{% load static %}','').replace(/\{% static '([^']+)' %\}/g,(_,n)=>'/static/'+n).replace('{{ token }}',token);
const docs=Object.fromEntries(['synthetic-original.docx','synthetic-with-codes.docx'].map(n=>[n,fs.readFileSync(path.join(downloads,n))]));
const report={scope:'Actual authenticated browser downloads rendered with bundled docx-preview; approximate HTML, not native Word certification.',provider_calls:0,cases:[],errors:[],external_requests:[]};
let origin,browser;
const server=http.createServer((req,res)=>{
  const u=new URL(req.url,origin);let body,type='text/html';
  if(u.pathname==='/frame'){
    body=frame;res.setHeader('Content-Security-Policy',`default-src 'none'; script-src ${origin}; style-src ${origin} 'unsafe-inline'; img-src data: blob:; font-src data: blob:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; sandbox allow-scripts`);
  }else if(assets[u.pathname]){body=assets[u.pathname];type=u.pathname.endsWith('.css')?'text/css':'application/javascript';}
  else if(u.pathname==='/doc'&&docs[u.searchParams.get('name')]){body=docs[u.searchParams.get('name')];type='application/vnd.openxmlformats-officedocument.wordprocessingml.document';}
  else if(u.pathname==='/observe.js'){body="window.results=[];addEventListener('message',e=>{if(e.data?.type==='blank-form-preview-result')results.push(e.data);});";type='application/javascript';}
  else if(u.pathname==='/'){
    const width=Number(u.searchParams.get('width')),name=u.searchParams.get('name');
    if(!docs[name]||![1100,375].includes(width)){res.statusCode=400;res.end();return;}
    body=`<!doctype html><meta charset="utf-8"><title>Downloaded synthetic Word · approximate preview</title><script src="/observe.js" defer></script><script src="/static/template-review.js" defer></script><script src="/static/template-preparation.js" defer></script><body><div data-preparation data-state="review"><h1>Downloaded synthetic Word · approximate preview</h1><section><p data-preview-status>Loading…</p><iframe title="Downloaded synthetic Word" sandbox="allow-scripts" width="${width}" height="1300" src="/frame" data-token="${token}" data-docx-url="/doc?name=${name}"></iframe></section></div></body>`;
  }else{res.statusCode=404;body='Not found';}
  res.setHeader('Content-Type',type);res.setHeader('Cache-Control','no-store');res.end(body);
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1240,height:1500}});
  await context.route('**/*',r=>{if(r.request().url().startsWith(origin+'/'))return r.continue();report.external_requests.push(r.request().url());return r.abort();});
  const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  for(const name of Object.keys(docs))for(const width of [1100,375]){
    await page.goto(origin+'/?name='+name+'&width='+width);await page.waitForFunction(()=>window.results?.length===1,null,{timeout:15000});
    const result=await page.evaluate(()=>results[0]);assert.equal(result.ok,true);assert.equal(result.approximate,true);
    const child=page.frames().find(f=>f!==page.mainFrame());
    const pages=await child.locator('.preview-page').evaluateAll(elements=>elements.map(e=>({text:e.innerText,
      width:Number(e.dataset.naturalWidth),height:Number(e.dataset.naturalHeight),scale:Number(e.dataset.previewScale),
      visible_width:e.getBoundingClientRect().width,article_height:e.querySelector('article').getBoundingClientRect().height/Number(e.dataset.previewScale),
      sections:[...e.querySelectorAll('article')].map(a=>({text:a.innerText,top:a.getBoundingClientRect().top,bottom:a.getBoundingClientRect().bottom}))})));
    assert.ok(pages.every(p=>p.visible_width<=width+1));assert.equal(result.expanded_page_count,0);
    report.cases.push({name,width,result,pages});await page.screenshot({path:path.join(out,name+'-'+width+'.png'),fullPage:true});
  }
  const [original,originalMobile,coded,codedMobile]=report.cases;
  assert.equal(original.pages.length,1);
  const oldSections=original.pages.flatMap(p=>p.sections),newSections=coded.pages.flatMap(p=>p.sections);
  assert.equal(oldSections.length,1);assert.equal(newSections.length,2);
  assert.equal(oldSections[0].text,newSections[0].text.trim());
  assert.match(newSections[1].text,/Diagnosis and procedure codes/);assert.match(newSections[1].text,/R12 — Heartburn/);
  assert.doesNotMatch(newSections[1].text,/K59|99213|15 MINUTES/);
  assert.ok(newSections[1].top>=newSections[0].bottom);
  // This bundled renderer's isPageBreakSection compares orientation and paper
  // dimensions only, ignoring nextPage for same-size sections. Preserve and
  // disclose that limit rather than modifying a correct Word section for HTML.
  report.pagination={word_sections:2,html_preview_pages:coded.pages.length,native_word_verified:false,
    limitation:'Bundled docx-preview joins same-size nextPage sections. XML retains an explicit nextPage section; native Word pagination remains unverified.'};
  for(const [a,b] of [[original,originalMobile],[coded,codedMobile]]){
    assert.equal(a.pages.length,b.pages.length);
    a.pages.forEach((p,i)=>{assert.equal(p.text,b.pages[i].text);assert.ok(Math.abs(p.article_height-b.pages[i].article_height)<.2);});
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external_requests,[]);report.verdict='PASS';
})().catch(e=>{report.verdict='FAIL';report.failure=String(e);process.exitCode=1;}).finally(async()=>{
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2),{mode:0o600});await browser?.close();server.close();console.log(JSON.stringify({verdict:report.verdict,failure:report.failure,output:out}));
});
