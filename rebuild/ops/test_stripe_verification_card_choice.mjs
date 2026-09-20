import assert from 'node:assert/strict';
import {test} from 'node:test';
import {chromium} from '@playwright/test';
import {prepareHostedCardChoice} from './stripe_verification_card_choice.mjs';

function fixture({visible = false, active = false, unrelated = false, descendant = false} = {}) {
  return `<!doctype html><style>
    #choice {position:relative;width:240px;height:60px;margin:20px;}
    #payment-method-accordion-item-title-card {position:absolute;top:20px;left:20px;width:20px;height:20px;margin:0;}
    #card-overlay {position:absolute;top:0;left:0;width:0;height:0;margin:0;padding:0;border:0;}
    #card-overlay::after {content:"";position:absolute;top:0;left:0;width:240px;height:60px;}
    #card-overlay span {position:absolute;top:0;left:0;width:240px;height:60px;z-index:1;}
    #unrelated {position:absolute;top:0;left:0;width:240px;height:60px;z-index:2;}
    #cardNumber {display:${visible ? 'block' : 'none'};}
  </style>
  <button id="usd" ${active ? 'disabled class="is-active"' : ''}>$5.00</button>
  <div id="choice"><input type="radio" id="payment-method-accordion-item-title-card" name="method">
    <button id="card-overlay" data-testid="card-accordion-item-button" aria-label="Pay with card">${descendant ? '<span></span>' : ''}</button>
    ${unrelated ? '<button id="unrelated">Unrelated action</button>' : ''}
  </div><input id="cardNumber">
  <script>
    window.actions=[];
    document.querySelector('#usd').onclick = function(){actions.push('usd');this.classList.add('is-active');this.disabled=true;};
    document.querySelector('#card-overlay').onclick = function(){actions.push('card');document.querySelector('#cardNumber').style.display='block';document.querySelector('input[type=radio]').checked=true;};
    document.querySelector('#unrelated')?.addEventListener('click',()=>actions.push('unrelated'));
  </script>`;
}

test('hosted card-choice guard uses the real pointer target without payment submission', async t => {
  const browser = await chromium.launch({headless: true});
  const run = async (options, check) => {
    const page = await browser.newPage();
    try {await page.setContent(fixture(options)); await check(page);} finally {await page.close();}
  };
  try {
    await t.test('hidden-box Card overlay defeats check but guarded natural pointer opens fields', () => run({}, async page => {
      assert.equal(await page.locator('#card-overlay').isVisible(), false);
      await assert.rejects(page.locator('input[type=radio]').check({timeout: 300}), {name: 'TimeoutError'});
      const result = await prepareHostedCardChoice(page, {timeout: 2000});
      assert.deepEqual(result, {currency_action: 'clicked-usd', card_action: 'clicked-card-radio-position'});
      assert.equal(await page.locator('#cardNumber').isVisible(), true);
      assert.deepEqual(await page.evaluate(() => actions), ['usd', 'card']);
    }));
    await t.test('active disabled USD and visible Card fields need no clicks', () => run({visible: true, active: true}, async page => {
      assert.deepEqual(await prepareHostedCardChoice(page), {currency_action: 'already-active-usd', card_action: 'already-visible'});
      assert.deepEqual(await page.evaluate(() => actions), []);
    }));
    await t.test('unrelated overlay is refused without activating it', () => run({active: true, unrelated: true}, async page => {
      await assert.rejects(prepareHostedCardChoice(page), /unrelated overlay/);
      assert.deepEqual(await page.evaluate(() => actions), []);
      assert.equal(await page.locator('#cardNumber').isVisible(), false);
    }));
    await t.test('a descendant of the identified Card control is allowed', () => run({active: true, descendant: true}, async page => {
      await prepareHostedCardChoice(page);
      assert.deepEqual(await page.evaluate(() => actions), ['card']);
    }));
    await t.test('disabled unselected USD is refused', () => run({visible: true}, async page => {
      await page.locator('#usd').evaluate(button => {button.disabled = true;});
      await assert.rejects(prepareHostedCardChoice(page), /not selected/);
      assert.deepEqual(await page.evaluate(() => actions), []);
    }));
    await t.test('ambiguous USD options are refused', () => run({visible: true}, async page => {
      await page.locator('#usd').evaluate(button => button.after(button.cloneNode(true)));
      await assert.rejects(prepareHostedCardChoice(page), /ambiguous/);
      assert.deepEqual(await page.evaluate(() => actions), []);
    }));
  } finally {await browser.close();}
});
