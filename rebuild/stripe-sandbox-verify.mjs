/**
 * Stripe SANDBOX verification through the private doctor UI and Stripe-hosted
 * Checkout. Synthetic doctor only, Stripe test cards only, never an automatic
 * checkout retry. Run from the permanent reviewed release, as the operator:
 *
 *   node rebuild/stripe-sandbox-verify.mjs --release FULL_SHA --dry-run
 *   node rebuild/stripe-sandbox-verify.mjs --release FULL_SHA --execute
 *
 * --dry-run validates every precondition, records the wallet baseline and
 * writes a report with executed:false. It never submits a checkout.
 *
 * Required for --execute: STRIPE_CLI=/absolute/path/to/stripe enables event lookup,
 * duplicate delivery and refund cases through the OPERATOR's own CLI login
 * (a separate capability; the application key never leaves the service).
 * PLAYWRIGHT_MODULE_DIR may locate existing installed browser dependencies.
 *
 * Signed event forwarding is started SEPARATELY by the operator before this
 * runner and is not started, stopped or inspected here:
 *
 *   stripe listen --forward-to http://127.0.0.1:9130/billing/webhook/ \
 *     --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,refund.created,refund.updated,refund.failed
 *
 * Its whsec_… signing secret must already be STRIPE_WEBHOOK_SECRET in the
 * application's protected environment. This runner never reads, prints or
 * receives that secret, the API key, card data or the hosted checkout URL.
 * Only Stripe object identifiers (cs_test_…, pi_…, evt_…, re_…) and the
 * application's own payment identifiers are recorded.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import constants from 'node:constants';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {requireExecutionCLI, verificationOutcome} from './ops/stripe_verification_outcome.mjs';

const app=path.dirname(fileURLToPath(import.meta.url));
const permanent='/opt/meddoc-pro/rebuild';
// The service listens on 127.0.0.1:9130. Its Stripe success_url and cancel_url
// are fixed to http://localhost:9130 (core/views.py checkout). Both names reach
// the same loopback listener; the health check below proves it for this run.
// Session cookies are host-scoped and SameSite=Strict, so the browser lands on
// localhost UNAUTHENTICATED after Stripe redirects it. That is the product's
// documented behaviour ("A checkout redirect does not grant balance"); the
// runner observes the landing URL and returns to 127.0.0.1 where its session is.
const base='http://127.0.0.1:9130';
const alias='http://localhost:9130';
const appOrigins=new Set([base,alias]);
// Stripe-hosted Checkout loads its page from checkout.stripe.com and its
// static assets, fonts and fraud-signal frames from Stripe-operated hosts under
// these suffixes. Every other origin is aborted and counted in the report;
// every allowed non-application host is counted too, so the actual set that
// was contacted is evidence rather than an assumption.
const stripeHostSuffixes=['.stripe.com','.stripecdn.com','.stripe.network'];
const LISTEN_COMMAND='stripe listen --forward-to http://127.0.0.1:9130/billing/webhook/ --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,refund.created,refund.updated,refund.failed';
// Stripe's published test cards; they are not secrets and never reach the report.
const CARD_SUCCESS='4242424242424242';
const CARD_DECLINED='4000000000000002';
const CHECKOUT_EMAIL='stripe-sandbox@synthetic.quillmd.invalid';
const TOP_UP_USD='5.00';
const TOP_UP_MICRO=5000000n;
const REFUND_CENTS=200;
const REFUND_MICRO=2000000n;
const MAX_CHECKOUTS=2;

const args=process.argv.slice(2);
const value=name=>{const i=args.indexOf(name);return i>=0?args[i+1]:undefined;};
const release=value('--release');
const execute=args.includes('--execute');
const dryRun=args.includes('--dry-run');
const mode=execute?'execute':'dry-run';
const stripeCli=process.env.STRIPE_CLI||'';

const report={passed:false,executed:false,execution_completed:false,sandbox_acceptance:'not attempted',mode,release,synthetic_only:true,app_origins:[base,alias],
  checks:[],checkout_submissions:0,refused_checkout_posts:0,refused_provider_posts:0,
  blocked_requests:{count:0,hosts:{}},stripe_hosts_contacted:{},
  card_data_stored:false,checkout_url_stored:false,webhook_secret_read:false,api_key_read:false,
  stripe_listen:{started_by_runner:false,required_command:LISTEN_COMMAND,
    verified_by:'operator terminal output; forwarding is not observable from the doctor UI'},
  stripe_cli:{configured:Boolean(stripeCli),invocations:[]},
  stripe_ids:{},
  cases:{
    payment_success:{status:'not run'},
    duplicate_delivery:{status:'not run'},
    refund:{status:'not run'},
    failed_payment:{status:'not run'},
    retry_after_receiver_failure:{status:'manual',
      how:'Engineering must record a controlled failed forwarding attempt followed by receipt of the same authentic event, then confirm wallet and ledger invariants. Use the runbook; do not interrupt the application service.'},
    out_of_order_delivery:{status:'manual',
      how:'Not automated by this runner. Engineering must control delivery order of authentic sandbox events and record receiver attempts plus wallet/ledger results. Locally signed lifecycle tests are isolated evidence only.'},
    concurrent_spending:{status:'not covered by this runner',
      how:'Requires a live generation reservation racing a refund; use the isolated test suite\'s concurrent refund cases and a supervised session.'},
  }};
let stage='argument and private-file validation';
let browser,reportPath,checkoutArmed=false,wroteReport=false,credentials;

async function privateJSON(filename,document){
  const file=await fs.open(filename,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
  try{await file.writeFile(JSON.stringify(document,null,2)+'\n');await file.sync();}finally{await file.close();}
}
async function privateRead(filename){
  assert.equal(await fs.realpath(filename),filename);
  const file=await fs.open(filename,constants.O_RDONLY|constants.O_NOFOLLOW);
  try{
    const info=await file.stat();
    assert(info.isFile() && info.nlink===1 && info.uid===process.getuid() && (info.mode&0o777)===0o600 && info.size<=2*1024*1024);
    return JSON.parse(await file.readFile('utf8'));
  }finally{await file.close();}
}
async function check(name,action){stage=name;await action();report.checks.push({name,passed:true});console.log('PASS '+name);}
function count(map,key){if(!(key in map)&&Object.keys(map).length>=50)key='(other)';map[key]=(map[key]||0)+1;}
function stripeHost(hostname){return stripeHostSuffixes.some(suffix=>hostname===suffix.slice(1)||hostname.endsWith(suffix));}
// Exact micro-dollar arithmetic on the six-decimal strings the billing page renders.
function micro(text){const m=/^\$?(-?)(\d+)\.(\d{6})$/.exec(String(text).trim());assert(m,'Unrecognised balance format on the billing page.');const v=BigInt(m[2])*1000000n+BigInt(m[3]);return m[1]?-v:v;}
function usd(v){const negative=v<0n;const a=negative?-v:v;return (negative?'-':'')+(a/1000000n).toString()+'.'+(a%1000000n).toString().padStart(6,'0');}
function futureExpiry(){const year=new Date().getUTCFullYear()+3;return '12/'+String(year%100).padStart(2,'0');}

async function guardedContext(){
  const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:false});
  await context.route('**/*',async route=>{
    const request=route.request();const url=new URL(request.url());
    if(appOrigins.has(url.origin)){
      if(request.method()==='POST'){
        if(url.pathname==='/billing/checkout/'){
          // Exactly the armed submissions, never a repeat: an uncertain checkout is
          // inspected by a person, not retried by a script.
          if(!checkoutArmed||report.checkout_submissions>=MAX_CHECKOUTS){report.refused_checkout_posts++;await route.abort('blockedbyclient');return;}
          checkoutArmed=false;report.checkout_submissions++;report.executed=true;
          report.sandbox_acceptance='incomplete';
        }else if(/^\/encounters\/[0-9a-f-]+\/(generate|voice)\/$/.test(url.pathname)){report.refused_provider_posts++;await route.abort('blockedbyclient');return;}
      }
      await route.continue();return;
    }
    if(url.protocol==='https:'&&stripeHost(url.hostname)){count(report.stripe_hosts_contacted,url.hostname);await route.continue();return;}
    report.blocked_requests.count++;count(report.blocked_requests.hosts,url.hostname);await route.abort('blockedbyclient');
  });
  return context;
}
async function login(page,account){
  assert(account && account.email.endsWith('@synthetic.quillmd.invalid') && typeof account.password==='string');
  await page.goto(base+'/login/');
  await page.locator('[name=email]').fill(account.email);
  await page.locator('[name=password]').fill(account.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.waitForURL(base+'/');
}
// Everything the doctor billing page shows, read from the rendered DOM.
async function snapshot(page){
  await page.goto(base+'/billing/');
  assert.equal(new URL(page.url()).pathname,'/billing/','Billing page unavailable; the session may have expired.');
  return page.evaluate(()=>{
    const text=el=>(el?.textContent||'').trim();
    const section=name=>[...document.querySelectorAll('section.section')].find(s=>[...s.querySelectorAll('h2')].some(h=>text(h)===name));
    const rows=s=>s?[...s.querySelectorAll('tbody tr')].map(tr=>[...tr.cells].map(text)):[];
    return {
      wallets:[...document.querySelectorAll('.balance-item')].map(item=>({label:text(item.querySelector('h2')),balance:text(item.querySelector('.balance-value')),reserved:text(item.querySelector('p'))})),
      ledger:rows(section('Account ledger')).map(c=>({kind:c[0],amount:c[2]})),
      payments:rows(section('Payment history')).map(c=>({id:c[0],wallet:c[1],status:c[2],amount:c[3]})),
      integrations:[...document.querySelectorAll('.integration-list li')].map(li=>({name:text(li.querySelector('strong')),status:text(li.querySelector('.badge'))})),
      checkout_forms:document.querySelectorAll('form[action="/billing/checkout/"]').length,
      notices:[...document.querySelectorAll('.message-list .notice')].map(text),
    };
  });
}
function wallet(snap,kind){
  const label=`${kind} · ${credentials.doctor.email}`;
  const found=snap.wallets.filter(w=>w.label===label);
  assert.equal(found.length,1,'Personal '+kind.toLowerCase()+' wallet is not shown exactly once.');
  return micro(found[0].balance);
}
function ledgerCount(snap,kind,amount){return snap.ledger.filter(row=>row.kind===kind&&micro(row.amount)===amount).length;}
function balances(snap){return {promo:usd(wallet(snap,'Promotional')),paid:usd(wallet(snap,'Paid')),payment_entries:ledgerCount(snap,'payment',TOP_UP_MICRO),refund_entries:ledgerCount(snap,'refund',-REFUND_MICRO),payments:snap.payments.length};}
async function poll(page,seconds,predicate){
  const deadline=Date.now()+seconds*1000;let snap;
  while(Date.now()<deadline){snap=await snapshot(page);if(predicate(snap))return snap;await page.waitForTimeout(2000);}
  return null;
}
// Fill the first visible candidate. Values are never logged or recorded.
async function fillFirst(page,label,selectors,text,{optional=false,timeout=20000}={}){
  const deadline=Date.now()+timeout;
  while(Date.now()<deadline){
    for(const selector of selectors){
      const locator=page.locator(selector).first();
      if(await locator.isVisible().catch(()=>false)){await locator.fill(text);return true;}
    }
    await page.waitForTimeout(400);
  }
  if(optional)return false;
  throw new Error('Hosted checkout field not found: '+label);
}
async function selectFirst(page,selectors,option){
  for(const selector of selectors){
    const locator=page.locator(selector).first();
    if(await locator.isVisible().catch(()=>false)){await locator.selectOption(option).catch(()=>{});return true;}
  }
  return false;
}
function sessionIdFromCheckoutURL(uri){
  const url=new URL(uri);assert.equal(url.hostname,'checkout.stripe.com');
  const match=url.pathname.match(/\/(cs_test_[A-Za-z0-9]+)/);assert(match,'Hosted checkout URL did not carry a test session identifier.');
  return match[1]; // The path id only; the fragment/query of the URL is never kept.
}
// Submit the application's own checkout form once and land on hosted checkout.
async function startCheckout(page,caseName){
  const before=await snapshot(page);
  assert.equal(before.checkout_forms,1,'The billing page does not offer checkout.');
  await page.locator('form[action="/billing/checkout/"] [name=payer]').selectOption('personal');
  await page.locator('form[action="/billing/checkout/"] [name=amount]').fill(TOP_UP_USD);
  await page.locator('form[action="/billing/checkout/"] [name=consent]').check();
  checkoutArmed=true;
  await page.getByRole('button',{name:'Continue to Stripe',exact:true}).click();
  await page.waitForURL(url=>url.hostname==='checkout.stripe.com'||(appOrigins.has(url.origin)&&url.pathname==='/billing/'),{timeout:45000});
  checkoutArmed=false;
  if(new URL(page.url()).hostname!=='checkout.stripe.com'){
    // The application refused or could not confirm the session; its notice is a
    // fixed product string and is safe evidence. Nothing is retried.
    const after=await snapshot(page);
    report.cases[caseName].application_notices=after.notices;
    throw new Error('Checkout did not reach Stripe-hosted checkout.');
  }
  return {before,session:sessionIdFromCheckoutURL(page.url())};
}
async function hostedCheckoutPay(page,cardNumber){
  await fillFirst(page,'email',['#email','[name=email]','input[type=email]'],CHECKOUT_EMAIL);
  const cardVisible=await page.locator('#cardNumber, [name=cardNumber], [autocomplete="cc-number"]').first().isVisible().catch(()=>false);
  if(!cardVisible){
    for(const selector of ['[data-testid="card-accordion-item-button"]','#card-tab','button:has-text("Card")']){
      const locator=page.locator(selector).first();
      if(await locator.isVisible().catch(()=>false)){await locator.click();break;}
    }
  }
  await fillFirst(page,'card number',['#cardNumber','[name=cardNumber]','[autocomplete="cc-number"]'],cardNumber);
  await fillFirst(page,'card expiry',['#cardExpiry','[name=cardExpiry]','[autocomplete="cc-exp"]'],futureExpiry());
  await fillFirst(page,'card cvc',['#cardCvc','[name=cardCvc]','[autocomplete="cc-csc"]'],'123');
  await fillFirst(page,'cardholder name',['#billingName','[name=billingName]','[autocomplete="cc-name"]'],'Synthetic Doctor');
  await selectFirst(page,['#billingCountry','[name=billingCountry]'],'US');
  await fillFirst(page,'postal code',['#billingPostalCode','[name=billingPostalCode]','[autocomplete="postal-code"]'],'94103',{optional:true,timeout:3000});
  const submit=page.locator('button[type=submit]').filter({hasText:/pay/i}).first();
  if(await submit.isVisible().catch(()=>false))await submit.click();else await page.locator('.SubmitButton').first().click();
}
function cli(commandArgs,timeout=60000){
  // The operator's own CLI login is used. Only PATH/HOME/config location reach
  // the child; no application or provider credential is inherited.
  const env={PATH:process.env.PATH||'/usr/local/bin:/usr/bin:/bin',HOME:process.env.HOME||'',LANG:'C.UTF-8'};
  if(process.env.XDG_CONFIG_HOME)env.XDG_CONFIG_HOME=process.env.XDG_CONFIG_HOME;
  const result=spawnSync(stripeCli,commandArgs,{encoding:'utf8',timeout,maxBuffer:8*1024*1024,env,stdio:['ignore','pipe','ignore']});
  const record={command:['stripe',...commandArgs].join(' '),exit:result.status,timed_out:Boolean(result.error&&result.error.code==='ETIMEDOUT')};
  report.stripe_cli.invocations.push(record);
  let parsed=null;
  if(result.status===0){try{parsed=JSON.parse(result.stdout);}catch{record.stdout_json=false;}}
  return {ok:result.status===0&&parsed!==null,parsed};
}
function findCompletedEvent(listing,sessionId){
  const rows=Array.isArray(listing?.data)?listing.data:[];
  for(const event of rows){
    const object=event?.data?.object;
    if(event?.type==='checkout.session.completed'&&object?.id===sessionId&&event.livemode===false){
      return {event_id:String(event.id),payment_intent:typeof object.payment_intent==='string'?object.payment_intent:null,payment_status:object.payment_status};
    }
  }
  return null;
}

try{
  assert(args.length===3&&/^[a-f0-9]{40}$/.test(release||'')&&(execute!==dryRun),'Usage: --release FULL_SHA with exactly one of --execute or --dry-run.');
  assert.deepEqual([...args].filter(x=>x.startsWith('--')).sort(),['--'+mode,'--release']);
  assert.equal(app,permanent,'Use the reviewed permanent release after activation.');
  assert.equal(await fs.realpath(app),app);
  const runtime=path.join(app,'.runtime');const info=await fs.lstat(runtime);
  assert(info.isDirectory()&&!info.isSymbolicLink()&&info.uid===process.getuid()&&(info.mode&0o777)===0o700);
  credentials=await privateRead(path.join(runtime,'private-access.json'));
  assert(credentials.doctor&&credentials.doctor.email.endsWith('@synthetic.quillmd.invalid'));
  // Exclusive evidence deliberately survives failures: an uncertain paid
  // request is inspected by a person before any new attempt is possible.
  reportPath=path.join(runtime,'stripe-sandbox-verification-'+release.slice(0,12)+(execute?'':'-dry-run')+'.json');
  assert(!(await fs.lstat(reportPath).then(()=>true,()=>false)),'Existing verification evidence requires inspection before another attempt.');
  stage='Operator CLI required for sandbox execution';
  requireExecutionCLI(execute,stripeCli);
  if(stripeCli){
    assert(path.isAbsolute(stripeCli)&&await fs.realpath(stripeCli)===stripeCli,'STRIPE_CLI must be the absolute real path of the Stripe CLI binary.');
    const meta=await fs.stat(stripeCli);assert(meta.isFile()&&(meta.mode&0o111),'STRIPE_CLI is not an executable file.');
  }
  // Playwright API debug output can include fill() arguments. Keep credential
  // and card handling quiet even if the invoking shell enabled debug logging.
  delete process.env.DEBUG;delete process.env.PWDEBUG;
  const require=createRequire(import.meta.url);
  const dependency=name=>process.env.PLAYWRIGHT_MODULE_DIR?require(path.resolve(process.env.PLAYWRIGHT_MODULE_DIR,name)):require(name);
  const {chromium}=dependency('@playwright/test');
  browser=await chromium.launch({headless:true});
  const context=await guardedContext();const page=await context.newPage();page.setDefaultTimeout(30000);

  await check('Both loopback names serve the exact synthetic-only doctor release',async()=>{
    for(const origin of appOrigins){
      const response=await context.request.get(origin+'/health/',{maxRedirects:0});assert.equal(response.status(),200);
      const health=await response.json();assert.equal(health.release,release);assert.equal(health.data_mode,'synthetic-only');assert.equal(health.surface,'doctor');
    }
  });
  await check('Signed-event receiver is configured (unsigned probe is rejected, not unavailable)',async()=>{
    // 503 means STRIPE_WEBHOOK_SECRET is absent in the running service; 400 means
    // a secret is configured and the unsigned body was refused by signature check.
    const response=await context.request.post(base+'/billing/webhook/',{data:'{}',headers:{'Content-Type':'application/json'},maxRedirects:0});
    report.webhook_probe_status=response.status();
    assert.notEqual(response.status(),503,'STRIPE_WEBHOOK_SECRET is not configured in the running service.');
    assert.equal(response.status(),400,'Unexpected receiver response to an unsigned probe.');
  });
  let baseline;
  await check('Synthetic doctor login, sandbox key badge and checkout form present',async()=>{
    await login(page,credentials.doctor);
    baseline=await snapshot(page);
    const payments=baseline.integrations.find(item=>item.name==='Payments');
    assert(payments,'Payments integration row is missing.');
    report.payments_badge=payments.status;
    assert.equal(payments.status,'Stripe sandbox key configured','The service reports no sandbox key; checkout would be refused.');
    assert.equal(baseline.checkout_forms,1,'Checkout form is not offered.');
    report.baseline=balances(baseline);
  });
  if(execute){
    let session,localPaymentId,afterPayment;
    await check('Case 1: one $5.00 personal checkout reaches Stripe-hosted checkout',async()=>{
      report.cases.payment_success.status='running';
      ({session}=await startCheckout(page,'payment_success'));
      report.stripe_ids.checkout_session_id=session;
    });
    await check('Case 1: Stripe test card is accepted and Stripe redirects to the application',async()=>{
      await hostedCheckoutPay(page,CARD_SUCCESS);
      await page.waitForURL(url=>appOrigins.has(url.origin)&&url.pathname==='/billing/'&&url.searchParams.get('payment')==='processing',{timeout:90000});
      const landed=new URL(page.url());
      report.cases.payment_success.success_redirect={origin:landed.origin,path:landed.pathname,query:'payment=processing',
        note:'Landing is unauthenticated by design (host-scoped Strict cookies); balance is read back on 127.0.0.1 with the existing session.'};
    });
    await check('Case 1: signed completion event credits the paid wallet exactly once',async()=>{
      const paidBefore=wallet(baseline,'Paid');
      afterPayment=await poll(page,180,snap=>{
        const created=snap.payments.filter(p=>!baseline.payments.some(b=>b.id===p.id));
        return created.length===1&&created[0].status==='paid'&&wallet(snap,'Paid')===paidBefore+TOP_UP_MICRO;
      });
      assert(afterPayment,'Payment did not settle within 180s: forwarding may not be running, the signing secret may not match, or the event needs reconciliation. Nothing was retried.');
      const created=afterPayment.payments.filter(p=>!baseline.payments.some(b=>b.id===p.id));
      localPaymentId=created[0].id;
      assert.equal(created[0].amount.replace(/\s/g,''),'500¢');
      assert.equal(wallet(afterPayment,'Promotional'),wallet(baseline,'Promotional'),'Promotional balance moved during a paid top-up.');
      assert.equal(ledgerCount(afterPayment,'payment',TOP_UP_MICRO),ledgerCount(baseline,'payment',TOP_UP_MICRO)+1,'Expected exactly one new payment ledger entry.');
      report.cases.payment_success={...report.cases.payment_success,status:'passed',local_payment_id:localPaymentId,stripe_checkout_session_id:session,
        paid_wallet_before:usd(paidBefore),paid_wallet_after:usd(wallet(afterPayment,'Paid')),credited:usd(TOP_UP_MICRO),
        note:'The doctor UI shows the application payment id; the Stripe session id was read from the hosted checkout URL path.'};
    });
    {
      let completed;
      await check('Case 2: CLI lists the completed session event and its payment intent',async()=>{
        report.cases.duplicate_delivery.status='running';
        const listing=cli(['events','list','--type','checkout.session.completed','--limit','20']);
        assert(listing.ok,'stripe events list failed; see stripe_cli.invocations.');
        completed=findCompletedEvent(listing.parsed,session);
        assert(completed,'The completed event for this session was not in the last 20 completed events.');
        assert(completed.payment_intent,'The session carries no payment intent identifier.');
        report.stripe_ids.completed_event_id=completed.event_id;report.stripe_ids.payment_intent_id=completed.payment_intent;
      });
      await check('Case 2: request duplicate resend and compare balances (arrival needs receiver evidence)',async()=>{
        const resend=cli(['events','resend',completed.event_id]);
        assert(resend.ok,'stripe events resend failed; see stripe_cli.invocations.');
        await page.waitForTimeout(12000);
        const after=await snapshot(page);
        assert.equal(wallet(after,'Paid'),wallet(afterPayment,'Paid'),'Paid balance changed after a duplicate delivery.');
        assert.equal(ledgerCount(after,'payment',TOP_UP_MICRO),ledgerCount(afterPayment,'payment',TOP_UP_MICRO),'A second payment ledger entry appeared.');
        assert.equal(after.payments.length,afterPayment.payments.length,'A new payment row appeared after a duplicate delivery.');
        report.cases.duplicate_delivery={status:'unverified delivery',event_id:completed.event_id,paid_wallet_unchanged:true,payment_ledger_entries:ledgerCount(after,'payment',TOP_UP_MICRO),
          arrival_confirmed_by_runner:false,
          limit:'The doctor UI cannot show receiver attempts. Confirm the resent event id produced a [200] POST line in the stripe listen terminal; without that line the unchanged balance is not evidence of idempotency.'};
      });
      let afterRefund;
      await check('Case 3: a $2.00 sandbox refund debits the paid wallet exactly once',async()=>{
        report.cases.refund.status='running';
        const refund=cli(['refunds','create','--payment-intent',completed.payment_intent,'--amount',String(REFUND_CENTS)]);
        assert(refund.ok,'stripe refunds create failed; the operator CLI needs refund write capability.');
        const refundId=typeof refund.parsed?.id==='string'?refund.parsed.id:null;assert(refundId&&refundId.startsWith('re_'),'No refund identifier returned.');
        report.stripe_ids.refund_id=refundId;report.cases.refund.provider_status_at_creation=String(refund.parsed.status||'');
        const paidBefore=wallet(afterPayment,'Paid');
        afterRefund=await poll(page,180,snap=>ledgerCount(snap,'refund',-REFUND_MICRO)===ledgerCount(afterPayment,'refund',-REFUND_MICRO)+1&&wallet(snap,'Paid')===paidBefore-REFUND_MICRO);
        assert(afterRefund,'Refund ledger entry did not appear within 180s. A refund needing reconciliation stays visible to administrators; nothing was retried.');
        assert.equal(wallet(afterRefund,'Promotional'),wallet(baseline,'Promotional'));
        report.cases.refund={...report.cases.refund,status:'passed',refund_id:refundId,payment_intent_id:completed.payment_intent,debited:usd(REFUND_MICRO),
          paid_wallet_before:usd(paidBefore),paid_wallet_after:usd(wallet(afterRefund,'Paid'))};
      });
      afterPayment=afterRefund;
    }
    await check('Case 4: a declined test card leaves the payment unpaid and the balance unchanged',async()=>{
      report.cases.failed_payment.status='running';
      const {before,session:declinedSession}=await startCheckout(page,'failed_payment');
      report.stripe_ids.declined_checkout_session_id=declinedSession;
      await hostedCheckoutPay(page,CARD_DECLINED);
      await page.getByText(/declined/i).first().waitFor({timeout:60000});
      assert.equal(new URL(page.url()).hostname,'checkout.stripe.com','Left hosted checkout after a decline.');
      const after=await snapshot(page);
      const created=after.payments.filter(p=>!before.payments.some(b=>b.id===p.id));
      assert.equal(created.length,1,'Expected exactly one new payment row for the declined attempt.');
      assert(['pending','processing'].includes(created[0].status),'Declined checkout is not pending: '+created[0].status);
      assert.equal(wallet(after,'Paid'),wallet(before,'Paid'),'Paid balance changed after a declined card.');
      assert.equal(wallet(after,'Promotional'),wallet(before,'Promotional'),'Promotional balance changed after a declined card.');
      assert.equal(ledgerCount(after,'payment',TOP_UP_MICRO),ledgerCount(before,'payment',TOP_UP_MICRO));
      report.cases.failed_payment={status:'passed',local_payment_id:created[0].id,stripe_checkout_session_id:declinedSession,payment_status_after_decline:created[0].status,
        paid_wallet_unchanged:true,decline_message_observed:true,
        follow_up:'The open session expires at Stripe within 24h and its checkout.session.expired event should move this payment row to expired; re-read the billing page then.'};
    });
    report.final=balances(await snapshot(page));
    report.execution_completed=true;
  }
  assert.equal(report.refused_checkout_posts,0);assert.equal(report.refused_provider_posts,0);
  assert.equal(report.checkout_submissions,execute?(MAX_CHECKOUTS):0);
  Object.assign(report,verificationOutcome(report));report.completed_at=new Date().toISOString();
  await privateJSON(reportPath,report);wroteReport=true;
  if(execute&&!report.passed)process.exitCode=2;
  console.log((execute?(report.passed?'Stripe sandbox verification passed.':'Stripe sandbox checks completed; acceptance INCOMPLETE.'): 'Stripe sandbox dry run passed; nothing was submitted.')+' Evidence: '+reportPath);
}catch(error){
  report.active_check=stage;report.error_class=error?.constructor?.name||'Error';
  report.error_line=String(error?.stack||'').split('\n').find(line=>/^\s*at\s/.test(line)&&line.includes('stripe-sandbox-verify.mjs'))?.trim()||'';
  if(reportPath&&!wroteReport)await privateJSON(reportPath,report).catch(()=>{});
  console.error('Stripe sandbox verification stopped at: '+stage+'. No checkout was retried; error details are suppressed.');
  process.exitCode=1;
}finally{await browser?.close();}
