(() => {
  'use strict';
  const token=document.body.dataset.previewToken;
  const body=document.getElementById('document-body');
  const fitButton=document.querySelector('[data-preview-fit]');
  const actualButton=document.querySelector('[data-preview-actual]');
  const pageStatus=document.querySelector('[data-preview-pages]');
  let rendered=false;
  let fit=true;
  let pages=[];
  let lastWidth=0;
  const stripNavigation=() => {
    document.querySelectorAll('a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('target');a.setAttribute('tabindex','-1');});
    document.querySelectorAll('form,iframe,object,embed').forEach(n=>n.remove());
    document.querySelectorAll('img').forEach(n=>{const src=n.getAttribute('src')||'';if(!src.startsWith('blob:')&&!src.startsWith('data:'))n.removeAttribute('src');});
  };
  new MutationObserver(stripNavigation).observe(body,{childList:true,subtree:true});
  document.addEventListener('click',e=>{if(e.target.closest('a'))e.preventDefault();},true);
  document.addEventListener('submit',e=>e.preventDefault(),true);
  const layoutPages=()=>{
    const available=Math.max(1,body.clientWidth);
    pages.forEach(({page,wrapper})=>{
      page.style.transform='none';
      const box=page.getBoundingClientRect();
      // Size at the original paper width, then scale the complete page. This
      // preserves wrapping even when two narrow comparison panels are visible.
      const width=box.width;
      const height=Math.max(box.height,page.scrollHeight);
      const scale=fit?Math.min(1,available/Math.max(1,width)):1;
      wrapper.style.width=(width*scale)+'px';
      wrapper.style.height=(height*scale)+'px';
      page.style.transform='scale('+scale+')';
      wrapper.dataset.naturalWidth=String(width);
      wrapper.dataset.naturalHeight=String(height);
      wrapper.dataset.previewScale=String(scale);
    });
    lastWidth=available;
  };
  const setFit=value=>{
    fit=value;
    if(fitButton)fitButton.setAttribute('aria-pressed',String(value));
    if(actualButton)actualButton.setAttribute('aria-pressed',String(!value));
    layoutPages();
  };
  if(fitButton)fitButton.addEventListener('click',()=>setFit(true));
  if(actualButton)actualButton.addEventListener('click',()=>setFit(false));
  new ResizeObserver(()=>{if(pages.length&&body.clientWidth!==lastWidth)layoutPages();}).observe(body);
  const settle=async()=>{
    // Embedded images/fonts affect geometry. Wait only for local rendered assets,
    // with a bounded deadline so an unavailable font cannot stall preparation.
    const assets=[...body.querySelectorAll('img')].map(img=>img.decode?img.decode().catch(()=>{}):Promise.resolve());
    if(document.fonts)assets.push(document.fonts.ready);
    await Promise.race([Promise.all(assets),new Promise(resolve=>setTimeout(resolve,1000))]);
    await Promise.race([new Promise(resolve=>requestAnimationFrame(resolve)),new Promise(resolve=>setTimeout(resolve,100))]);
  };
  window.addEventListener('message',async event=>{
    if(event.source!==window.parent||rendered||!event.data||event.data.token!==token||event.data.type!=='blank-form-preview')return;
    const bytes=event.data.bytes;
    if(!(bytes instanceof ArrayBuffer)||bytes.byteLength===0||bytes.byteLength>10*1024*1024)return;
    rendered=true;
    const started=performance.now();
    try {
      await window.docx.renderAsync(bytes,body,document.getElementById('document-styles'),{
        className:'blank-document',renderHeaders:true,renderFooters:true,renderFootnotes:true,renderEndnotes:true,
        renderAltChunks:false,renderChanges:false,renderComments:false,experimental:false,
        ignoreWidth:false,ignoreHeight:false,ignoreFonts:false,
        ignoreLastRenderedPageBreak:false,breakPages:true});
      stripNavigation();
      await settle();
      const sections=[...body.querySelectorAll('section.blank-document')];
      if(!sections.length)throw new Error('No preview pages');
      const expanded=sections.filter(page=>{
        const minimum=parseFloat(getComputedStyle(page).minHeight);
        return Number.isFinite(minimum)&&minimum>0&&Math.max(page.getBoundingClientRect().height,page.scrollHeight)>minimum+2;
      }).length;
      pages=sections.map((page,index)=>{
        const wrapper=document.createElement('div');
        wrapper.className='preview-page';
        wrapper.setAttribute('role','region');
        wrapper.setAttribute('aria-label','Approximate preview page '+(index+1));
        page.before(wrapper);wrapper.appendChild(page);
        return {page,wrapper};
      });
      layoutPages();
      if(fitButton)fitButton.disabled=false;
      if(actualButton)actualButton.disabled=false;
      if(pageStatus)pageStatus.textContent=pages.length+' approximate preview '+(pages.length===1?'page':'pages')+'. Download Word to check final pagination.';
      window.parent.postMessage({type:'blank-form-preview-result',token,ok:true,approximate:true,
        page_count:pages.length,expanded_page_count:expanded,
        elapsed_ms:Math.round(performance.now()-started)},'*');
    } catch(_) {
      body.textContent='This preview could not be rendered. Download the original and candidate to compare them in Word.';
      if(pageStatus)pageStatus.textContent='Preview unavailable.';
      window.parent.postMessage({type:'blank-form-preview-result',token,ok:false},'*');
    }
  });
  window.parent.postMessage({type:'blank-form-preview-ready',token},'*');
})();
