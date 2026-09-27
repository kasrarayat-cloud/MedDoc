// Render captured synthetic Django responses, with every network request blocked.
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('/opt/meddoc-pro/node_modules/playwright');
(async()=>{
 const directory=path.join(__dirname,'final-artifacts');
 const css=await fs.readFile(path.join(__dirname,'../..','static','app.css'),'utf8');
 const browser=await chromium.launch({headless:true});
 const results=[];
 try{
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
   const page=await browser.newPage({viewport:{width,height}});
   await page.route('**/*',route=>route.abort());
   const html=(await fs.readFile(path.join(directory,'mapping-review.html'),'utf8')).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<link\b[^>]*>/gi,'');
   await page.setContent(html);await page.addStyleTag({content:css});
   const result=await page.evaluate(()=>({
    heading:document.querySelector('h1')?.textContent,
    unresolved:document.querySelectorAll('select[name^="resolution_"]').length,
    unlabeled:[...document.querySelectorAll('select,input:not([type="hidden"])')].filter(el=>!el.labels?.length).length,
    bodyOverflow:document.documentElement.scrollWidth>window.innerWidth,
    minimumResolutionWidth:Math.min(...[...document.querySelectorAll('select[name^="resolution_"]')].map(el=>el.getBoundingClientRect().width)),
   }));
   if(result.heading!=='Mapping assistance'||!result.unresolved||result.unlabeled||result.bodyOverflow||result.minimumResolutionWidth<250)throw Error(JSON.stringify(result));
   await page.screenshot({path:path.join(directory,`mapping-review-${name}.png`),fullPage:true});
   results.push({viewport:name,...result});await page.close();
  }
  await fs.writeFile(path.join(__dirname,'render-review-final.json'),JSON.stringify({network:'all requests aborted',results},null,2)+'\n');
  process.stdout.write(JSON.stringify(results)+'\n');
 }finally{await browser.close();}
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1});
