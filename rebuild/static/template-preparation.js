(() => {
  'use strict';
  const root=document.querySelector('[data-preparation]');if(!root)return;
  const message=root.querySelector('[data-preparation-status]');
  const started=root.dataset.startedAt?Date.parse(root.dataset.startedAt):Date.now();
  const timer=root.querySelector('[data-elapsed]');
  const tick=()=>{if(timer)timer.textContent=Math.max(0,Math.floor((Date.now()-started)/1000))+' seconds elapsed';};
  tick();const interval=setInterval(tick,1000);
  if(['queued','inventory','proposer','checker'].includes(root.dataset.state)){
    let pending=false;
    const poll=setInterval(async()=>{
      if(pending)return;pending=true;
      try{const response=await fetch(root.dataset.statusUrl,{credentials:'same-origin',redirect:'error'});
        if(!response.ok)throw new Error();const result=await response.json();
        message.textContent={queued:'Waiting for the preparation worker',inventory:'Checking the complete original',proposer:'AI proposer is preparing answer areas',checker:'Independent AI checker is checking completeness and placement'}[result.state]||'Preparation finished';
        if(!['queued','inventory','proposer','checker'].includes(result.state)){clearInterval(poll);clearInterval(interval);window.location.reload();}
      }catch(_){clearInterval(poll);message.textContent='Status could not be checked. Reload this page to see the retained result.';}
      finally{pending=false;}
    },2500);
  }else clearInterval(interval);
  const frames=[...root.querySelectorAll('iframe[data-docx-url]')];
  window.addEventListener('message',async event=>{
    const frame=frames.find(f=>f.contentWindow===event.source);if(!frame||!event.data||event.data.token!==frame.dataset.token)return;
    const label=frame.parentElement.querySelector('[data-preview-status]');
    if(event.data.type==='blank-form-preview-ready'&&!frame.dataset.sent){
      frame.dataset.sent='yes';
      try{const response=await fetch(frame.dataset.docxUrl,{credentials:'same-origin',redirect:'error'});if(!response.ok)throw new Error();
        const bytes=await response.arrayBuffer();if(bytes.byteLength>10*1024*1024)throw new Error();
        frame.contentWindow.postMessage({type:'blank-form-preview',token:frame.dataset.token,bytes},'*',[bytes]);
      }catch(_){label.textContent='Preview unavailable. Use the download to review the complete Word file.';}
    }else if(event.data.type==='blank-form-preview-result'){
      label.textContent=event.data.ok?'Preview rendered. Compare every page with the original.':'Preview unavailable. Review the downloads in Word.';
      if(event.data.ok&&Number.isInteger(event.data.elapsed_ms))label.textContent+=' Render: '+event.data.elapsed_ms+' ms.';
    }
  });
})();
