(() => {
  'use strict';
  const token=document.body.dataset.previewToken;
  let rendered=false;
  const stripNavigation=() => {
    document.querySelectorAll('a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('target');a.setAttribute('tabindex','-1');});
    document.querySelectorAll('form,iframe,object,embed').forEach(n=>n.remove());
    document.querySelectorAll('img').forEach(n=>{const src=n.getAttribute('src')||'';if(!src.startsWith('blob:')&&!src.startsWith('data:'))n.removeAttribute('src');});
  };
  new MutationObserver(stripNavigation).observe(document.getElementById('document-body'),{childList:true,subtree:true});
  document.addEventListener('click',e=>{if(e.target.closest('a'))e.preventDefault();},true);
  document.addEventListener('submit',e=>e.preventDefault(),true);
  window.addEventListener('message',async event=>{
    if(event.source!==window.parent||rendered||!event.data||event.data.token!==token||event.data.type!=='blank-form-preview')return;
    const bytes=event.data.bytes;
    if(!(bytes instanceof ArrayBuffer)||bytes.byteLength===0||bytes.byteLength>10*1024*1024)return;
    rendered=true;
    const started=performance.now();
    try {
      await window.docx.renderAsync(bytes,document.getElementById('document-body'),document.getElementById('document-styles'),{
        className:'blank-document',renderHeaders:true,renderFooters:true,renderFootnotes:true,renderEndnotes:true,
        renderAltChunks:false,renderChanges:false,renderComments:false,experimental:false,
        ignoreLastRenderedPageBreak:false,breakPages:true});
      stripNavigation();
      window.parent.postMessage({type:'blank-form-preview-result',token,ok:true,elapsed_ms:Math.round(performance.now()-started)},'*');
    } catch(_) {
      document.getElementById('document-body').textContent='This preview could not be rendered. Download the original and candidate to compare them in Word.';
      window.parent.postMessage({type:'blank-form-preview-result',token,ok:false},'*');
    }
  });
  window.parent.postMessage({type:'blank-form-preview-ready',token},'*');
})();
