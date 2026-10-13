(() => {
  'use strict';
  const root=document.querySelector('[data-preparation]');if(!root)return;
  const message=root.querySelector('[data-preparation-status]');
  const started=root.dataset.startedAt?Date.parse(root.dataset.startedAt):Date.now();
  const timer=root.querySelector('[data-elapsed]');
  const tick=()=>{if(timer)timer.textContent=Math.max(0,Math.floor((Date.now()-started)/1000))+' seconds elapsed';};
  tick();const interval=setInterval(tick,1000);
  if(['queued','inventory','proposer','checker'].includes(root.dataset.state)){
    let pending=false,finished=false,failures=0,nextPoll;
    const poll=async()=>{
      if(pending||finished)return;pending=true;
      const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
      try{const response=await fetch(root.dataset.statusUrl,{credentials:'same-origin',redirect:'error',signal:controller.signal});
        if(!response.ok)throw new Error();const result=await response.json();
        if(!['queued','inventory','proposer','checker','review','guided','blocked','approved'].includes(result.state))throw new Error();
        failures=0;root.dataset.state=result.state;
        message.textContent={queued:'Waiting for the preparation worker',inventory:'Checking the complete original',proposer:'AI proposer is preparing answer areas',checker:'Independent AI checker is checking completeness and placement'}[result.state]||'Preparation finished';
        const coverage=root.querySelector('[data-preparation-coverage]');
        if(coverage&&Number.isInteger(result.field_count)&&result.field_count>0&&result.field_count<=100){
          coverage.textContent='All '+result.field_count+' detected answer fields are included. The original questions and answer locations stay intact.';
        }
        if(!['queued','inventory','proposer','checker'].includes(result.state)){finished=true;clearInterval(interval);window.location.reload();}
      }catch(_){failures++;message.textContent='Connection interrupted. Checking the retained preparation status again automatically; no new preparation is started.';}
      finally{clearTimeout(timeout);pending=false;if(!finished)nextPoll=setTimeout(poll,Math.min(15000,2500*2**Math.min(failures,3)));}
    };
    const resume=()=>{if(!finished&&!pending){clearTimeout(nextPoll);poll();}};
    window.addEventListener('online',resume);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)resume();});
    nextPoll=setTimeout(poll,2500);
  }else clearInterval(interval);
})();
