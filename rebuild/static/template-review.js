(() => {
  'use strict';
  const frames=[...document.querySelectorAll('iframe[data-docx-url]')];
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
      label.textContent=event.data.ok?'Approximate HTML preview. Compare all content with the original; check final pagination in the downloaded Word file.':'Preview unavailable. Review the downloads in Word.';
      if(event.data.ok&&Number.isInteger(event.data.page_count)&&event.data.page_count>0)label.textContent+=' '+event.data.page_count+' preview '+(event.data.page_count===1?'page.':'pages.');
      if(event.data.ok&&Number.isInteger(event.data.expanded_page_count)&&event.data.expanded_page_count>0)label.textContent+=' '+event.data.expanded_page_count+' preview '+(event.data.expanded_page_count===1?'page extends':'pages extend')+' beyond the stored paper height; Word may paginate differently.';
      if(event.data.ok&&Number.isInteger(event.data.elapsed_ms))label.textContent+=' Render: '+event.data.elapsed_ms+' ms.';
    }
  });

  const form=document.querySelector('[data-template-review]');
  if(!form)return;
  const consent=form.querySelector('[name="review_summary"]');
  const feedback=form.querySelector('[data-review-feedback]');
  const values=()=>JSON.stringify([...new FormData(form)].filter(([key])=>key.startsWith('field_')||key.startsWith('name_')||key.startsWith('decision_')));
  const baseline=values();
  form.querySelectorAll('[data-review-field]').forEach(row=>{
    const type=row.querySelector('[data-value-type]');
    const groups=[...row.querySelectorAll('[data-control-group]')];
    const updateGroups=()=>groups.forEach(group=>{
      const numeric=['integer','number'].includes(type.value);
      const filled=[...group.querySelectorAll('input,textarea')].some(input=>input.value.trim());
      const mode=group.querySelector('select');
      const applicable={unit:numeric, numeric, choices:type.value==='choice', mode:type.value==='text'}[group.dataset.controlGroup];
      // Never discard incompatible retained values. Expose them for an explicit
      // edit and let the unchanged server validators refuse invalid combinations.
      group.hidden=!(applicable||filled||(mode&&mode.value!=='atomic'));
    });
    if(type){type.addEventListener('change',updateGroups);updateGroups();}
    const question=row.querySelector('[data-name-subject]');
    const meaning=row.querySelector('[data-meaning]');
    if(question){
      const other=row.querySelector('[data-other-person]');
      const otherInput=other.querySelector('input');
      const subject=row.querySelector('[data-subject]');
      const original={meaning:meaning.value,subject:subject.value};
      let suggested=original.meaning;
      const choose=()=>{
        other.hidden=question.value!=='other';otherInput.required=question.value==='other';
        const role=question.value==='other'?otherInput.value.trim():question.value;
        subject.value=question.value||original.subject;
        const subjectSummary=row.querySelector('[data-subject-summary]');
        if(subjectSummary)subjectSummary.textContent=question.value?question.selectedOptions[0].textContent:'Person to confirm';
        const next=role?row.querySelector('h3').textContent+': the '+role+'’s name, as requested by this form.':original.meaning;
        if(meaning.value===suggested||meaning.value===original.meaning)meaning.value=next;
        suggested=next;
        row.querySelector('[data-meaning-summary]').textContent=meaning.value;
      };
      other.hidden=question.value!=='other';
      question.addEventListener('change',choose);otherInput.addEventListener('input',choose);
    }
    if(meaning)meaning.addEventListener('input',()=>{row.querySelector('[data-meaning-summary]').textContent=meaning.value;});
  });
  const changed=()=>values()!==baseline;
  form.addEventListener('input',event=>{
    if(event.target!==consent){consent.checked=false;feedback.textContent='Your edits are unsaved. Compare the definitions, confirm the summary and save decisions before approval.';}
  });
  form.addEventListener('change',event=>{
    if(event.target!==consent){consent.checked=false;feedback.textContent=changed()?'Your edits are unsaved. Confirm the summary and save decisions before approval.':'Ready to review the summary.';}
  });
  form.addEventListener('invalid',event=>{
    const details=event.target.closest('details');if(details)details.open=true;
  },true);
  form.addEventListener('submit',event=>{
    if(event.submitter?.hasAttribute('data-review-approve')&&changed()){
      event.preventDefault();event.stopImmediatePropagation();
      feedback.textContent='Save your edited definitions before approving this template.';
      feedback.scrollIntoView({block:'center'});
    }
  },true);
})();
