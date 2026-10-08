/* Bounded offline browser checks for the actual opaque Word-preview assets.
 * node rebuild/ops/test_docx_preview_browser.cjs /absolute/private/new-output-dir
 * This is renderer evidence, not authenticated acceptance or native Word layout.
 */
'use strict';
const fs=require('fs'),path=require('path'),http=require('http'),crypto=require('crypto'),assert=require('assert/strict');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),out=process.argv[2];
if(!out||!path.isAbsolute(out))throw Error('An absolute fresh private output directory is required.');
fs.mkdirSync(out,{mode:0o700});
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const JSZip=require(path.join(base,'static/vendor/docx-preview/jszip.min.js'));
const token='a'.repeat(48);
const assetNames=['static/docx-frame.js','static/docx-frame.css','static/template-preparation.js',
  'static/vendor/docx-preview/jszip.min.js','static/vendor/docx-preview/docx-preview.min.js'];
const assets=Object.fromEntries(assetNames.map(name=>['/'+name,fs.readFileSync(path.join(base,name))]));
const frameTemplate=fs.readFileSync(path.join(base,'templates/docx_preview_frame.html'),'utf8');
const frameHtml=frameTemplate.replace('{% load static %}','').replace(/\{% static '([^']+)' %\}/g,(_,name)=>'/static/'+name).replace('{{ token }}',token);
const report={format:'quillmd-docx-preview-browser-v1',started_at:new Date().toISOString(),scope:'Offline fixture browser using exact application frame and parent preview scripts. No authenticated acceptance, AI preparation, doctor review or native Word rendering.',
  provider_calls:0,db_writes:0,service_actions:0,original_document_writes:0,sources:assetNames.map(name=>({path:name,sha256:sha(assets['/'+name])})),cases:[],external_requests:[],errors:[]};
let origin='',browser,doc,canaryRequests=0;
const csp=()=>`default-src 'none'; script-src ${origin}; style-src ${origin} 'unsafe-inline'; img-src data: blob:; font-src data: blob:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; sandbox allow-scripts`;
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,origin);let raw,type='text/html';
  if(url.pathname==='/blocked-canary')canaryRequests++;
  if(url.pathname==='/frame'){raw=frameHtml;res.setHeader('Content-Security-Policy',csp());}
  else if(url.pathname==='/doc'){raw=doc;type='application/vnd.openxmlformats-officedocument.wordprocessingml.document';}
  else if(assets[url.pathname]){raw=assets[url.pathname];type=url.pathname.endsWith('.css')?'text/css':'application/javascript';}
  else if(url.pathname==='/observe.js'){raw="window.previewMessages=[];window.addEventListener('message',e=>{if(e.data?.type==='blank-form-preview-result')previewMessages.push({origin:e.origin,data:e.data});});";type='application/javascript';}
  else if(url.pathname==='/'){raw=`<!doctype html><html><head><meta charset="utf-8"><script src="/observe.js" defer></script><script src="/static/template-preparation.js" defer></script></head><body><div data-preparation data-state="review"><h1>Blank synthetic form preview</h1><section><p data-preview-status>Loading…</p><iframe title="Original blank form" sandbox="allow-scripts" referrerpolicy="no-referrer" width="${Number(url.searchParams.get('width'))||1100}" height="850" src="/frame" data-token="${token}" data-docx-url="/doc"></iframe></section></div></body></html>`;}
  else{res.statusCode=404;raw='Not found';}
  res.setHeader('Content-Type',type);res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Cache-Control','no-store');res.end(raw);
});
async function syntheticDocument(){
  const zip=new JSZip(),w='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  zip.file('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>');
  const rel=(id,type,target)=>`<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/${type}" Target="${target}"/>`;
  zip.file('_rels/.rels',`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${rel('r1','officeDocument','word/document.xml')}</Relationships>`);
  zip.file('word/_rels/document.xml.rels',`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${rel('rH','header','header1.xml')}${rel('rF','footer','footer1.xml')}<Relationship Id="rLink" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://attacker.invalid/" TargetMode="External"/></Relationships>`);
  const p=text=>`<w:p><w:r><w:t>${text}</w:t></w:r></w:p>`;
  zip.file('word/header1.xml',`<w:hdr xmlns:w="${w}">${p('SYNTHETIC HEADER — original retained')}</w:hdr>`);
  zip.file('word/footer1.xml',`<w:ftr xmlns:w="${w}">${p('SYNTHETIC FOOTER — original retained')}</w:ftr>`);
  zip.file('word/document.xml',`<w:document xmlns:w="${w}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${p('Page one — Temperature (°C): ______; Fever: Yes / No')}${p('This deliberately long line wraps at the original paper width and must retain identical geometry in narrow and wide previews. '.repeat(6))}<w:p><w:hyperlink r:id="rLink"><w:r><w:t>Navigation control — this text stays visible without an active link</w:t></w:r></w:hyperlink></w:p><w:p><w:r><w:br w:type="page"/><w:t>Page two — explicit manual break</w:t></w:r></w:p><w:p><w:r><w:lastRenderedPageBreak/><w:t>Page three — stored editor break</w:t></w:r></w:p>${p('Physician signature: __________')}<w:sectPr><w:headerReference w:type="default" r:id="rH"/><w:footerReference w:type="default" r:id="rF"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360"/></w:sectPr></w:body></w:document>`);
  return zip.generateAsync({type:'nodebuffer'});
}
async function inspect(page,width){
  const started=Date.now();await page.goto(origin+'/?width='+width,{waitUntil:'load',timeout:12000});
  await page.waitForFunction(()=>window.previewMessages?.length===1,null,{timeout:12000});
  const child=page.frames().find(frame=>frame!==page.mainFrame());
  const geometry=await child.evaluate(()=>({
    text:document.querySelector('#document-body').innerText,
    pages:[...document.querySelectorAll('.preview-page')].map(wrapper=>({
      natural_width:Number(wrapper.dataset.naturalWidth),natural_height:Number(wrapper.dataset.naturalHeight),scale:Number(wrapper.dataset.previewScale),visible_width:wrapper.getBoundingClientRect().width,
      header:wrapper.querySelector('header')?.innerText||'',footer:wrapper.querySelector('footer')?.innerText||'',article_height:wrapper.querySelector('article')?.getBoundingClientRect().height/Number(wrapper.dataset.previewScale),
    })),rendered_links:document.querySelectorAll('#document-body a').length,unsafe_elements:document.querySelectorAll('#document-body [href],#document-body form,#document-body iframe,#document-body object,#document-body embed').length,
    opaque:{parent_dom:(()=>{try{parent.document.body;return false;}catch(_){return true;}})(),storage:(()=>{try{localStorage.getItem('x');return false;}catch(_){return true;}})(),cookies:(()=>{try{document.cookie;return false;}catch(_){return true;}})()},
  }));
  const result=await page.evaluate(()=>previewMessages[0]);
  assert.equal(result.origin,'null');assert.equal(result.data.ok,true);assert.equal(result.data.approximate,true);
  assert.match(await page.locator('[data-preview-status]').innerText(),/Approximate HTML preview/);
  assert.equal(geometry.unsafe_elements,0);assert.ok(Object.values(geometry.opaque).every(Boolean));
  assert.equal(result.data.page_count,geometry.pages.length);assert.ok(geometry.pages.length>0);
  for(const sheet of geometry.pages){assert.ok(sheet.natural_width>0&&sheet.natural_height>0);assert.ok(sheet.visible_width<=width+1);}
  return {iframe_width:width,wall_ms:Date.now()-started,message:result.data,geometry};
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true,timeout:15000});report.browser_version=browser.version();
  const context=await browser.newContext({viewport:{width:1220,height:1000}});
  await context.route('**/*',route=>{if(route.request().url().startsWith(origin+'/'))return route.continue();report.external_requests.push(route.request().url());return route.abort();});
  const page=await context.newPage();page.on('pageerror',error=>report.errors.push(error.message));
  doc=await syntheticDocument();const before=sha(doc),wide=await inspect(page,1100),narrow=await inspect(page,375);
  assert.equal(wide.message.page_count,3);assert.equal(narrow.message.page_count,3);
  for(let i=0;i<wide.geometry.pages.length;i++){
    const a=wide.geometry.pages[i],b=narrow.geometry.pages[i];
    assert.ok(Math.abs(a.natural_width-b.natural_width)<.1);assert.ok(Math.abs(a.natural_height-b.natural_height)<.1);assert.ok(Math.abs(a.article_height-b.article_height)<.1);
    assert.match(a.header,/SYNTHETIC HEADER/);assert.match(a.footer,/SYNTHETIC FOOTER/);
  }
  assert.match(narrow.geometry.text,/Physician signature: __________/);assert.match(narrow.geometry.text,/Temperature \(°C\)/);assert.match(narrow.geometry.text,/Fever: Yes \/ No/);
  assert.equal(narrow.geometry.rendered_links,1);assert.match(narrow.geometry.text,/Navigation control/);
  assert.equal(sha(doc),before);
  const child=page.frames().find(frame=>frame!==page.mainFrame());
  await child.locator('[data-preview-actual]').click();
  assert.ok((await child.locator('.preview-page').evaluateAll(w=>w.map(x=>Number(x.dataset.previewScale)))).every(scale=>scale===1));
  await child.locator('[data-preview-fit]').click();
  assert.ok((await child.locator('.preview-page').evaluateAll(w=>w.map(x=>Number(x.dataset.previewScale)))).every(scale=>scale<1));
  report.connect_src_blocked=await child.evaluate(async url=>{try{await fetch(url);return false;}catch(_){return true;}},origin+'/blocked-canary');assert.equal(report.connect_src_blocked,true);
  report.canary_server_requests=canaryRequests;assert.equal(canaryRequests,0);
  await page.screenshot({path:path.join(out,'synthetic-narrow-fit.png'),fullPage:true});
  report.cases.push({name:'synthetic-source-breaks-header-footer-paper-width',original_sha256:before,original_unchanged:true,wide,narrow});
  const overflowZip=await JSZip.loadAsync(doc),documentXml=await overflowZip.file('word/document.xml').async('string');
  overflowZip.file('word/document.xml',documentXml.replace('<w:sectPr>','<w:p><w:r><w:t>Long unpaginated content — retained without clipping.</w:t></w:r></w:p>'.repeat(120)+'<w:sectPr>'));
  doc=await overflowZip.generateAsync({type:'nodebuffer'});const overflowSha=sha(doc),overflowWide=await inspect(page,1100),overflowNarrow=await inspect(page,375);
  assert.ok(overflowWide.message.expanded_page_count>0);assert.equal(overflowWide.message.expanded_page_count,overflowNarrow.message.expanded_page_count);
  assert.match(await page.locator('[data-preview-status]').innerText(),/beyond the stored paper height/);
  assert.equal((overflowNarrow.geometry.text.match(/Long unpaginated content/g)||[]).length,120);assert.equal(sha(doc),overflowSha);
  report.cases.push({name:'synthetic-height-overflow-is-retained-and-disclosed',original_sha256:overflowSha,original_unchanged:true,wide:overflowWide,narrow:overflowNarrow});
  // Retained authorized blank development forms, if supplied, are read-only.
  const corpus=process.env.QUILLMD_PREVIEW_CORPUS;
  if(corpus){const manifest=JSON.parse(fs.readFileSync(corpus));for(const form of manifest.forms){
    doc=fs.readFileSync(form.document);assert.equal(sha(doc),form.document_sha256);
    const a=await inspect(page,1100),b=await inspect(page,375);assert.equal(a.message.page_count,b.message.page_count);
    for(let i=0;i<a.geometry.pages.length;i++){assert.ok(Math.abs(a.geometry.pages[i].natural_width-b.geometry.pages[i].natural_width)<.1);assert.ok(Math.abs(a.geometry.pages[i].natural_height-b.geometry.pages[i].natural_height)<.1);}
    assert.equal(sha(fs.readFileSync(form.document)),form.document_sha256);
    if(form.name==='wm-iov'){assert.match(b.geometry.text,/Electronically Signed On/);assert.match(b.geometry.text,/INTERPRETING PHYSICIAN/);await page.screenshot({path:path.join(out,'wm-narrow-fit.png'),fullPage:true});}
    report.cases.push({name:form.name,original_sha256:form.document_sha256,original_unchanged:true,wide:a,narrow:b});
  }}
  assert.equal(report.external_requests.length,0);assert.equal(report.errors.length,0);report.complete=true;
})().catch(error=>{report.complete=false;report.failure={name:error.name,message:error.message,stack:error.stack};process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));report.finished_at=new Date().toISOString();
  fs.writeFileSync(path.join(out,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  console.log(JSON.stringify({complete:report.complete,cases:report.cases.map(c=>({name:c.name,pages:c.wide.message.page_count,wide_ms:c.wide.wall_ms,narrow_ms:c.narrow.wall_ms})),failure:report.failure?.message||null,output:out}));
});
