import assert from 'node:assert/strict';

// Select only the declared $5 USD option and Card method. This helper never
// receives card data or submits payment. A Stripe-owned accordion overlay can
// cover its visible radio while having an empty own box, defeating locator
// visibility/check(). Inspect the actual pointer target before a natural click.
export async function prepareHostedCardChoice(page, {timeout = 20000} = {}) {
  const result = {currency_action: 'not-offered', card_action: 'already-visible'};
  const usd = page.getByRole('button').filter({hasText: /\$5\.00/});
  const count = await usd.count();
  assert(count <= 1, 'USD choice is ambiguous.');
  if (count === 1 && await usd.isVisible()) {
    if (await usd.isEnabled()) {
      await usd.click({timeout});
      result.currency_action = 'clicked-usd';
    } else {
      assert(await usd.evaluate(button => button.classList.contains('is-active')), 'Disabled USD choice is not selected.');
      result.currency_action = 'already-active-usd';
    }
  }
  const number = page.locator('#cardNumber, [name=cardNumber], [autocomplete="cc-number"]').first();
  if (!await number.isVisible()) {
    const radio = page.locator('#payment-method-accordion-item-title-card');
    await radio.waitFor({state: 'visible', timeout});
    await radio.scrollIntoViewIfNeeded({timeout});
    const box = await radio.boundingBox();
    assert(box && box.width > 0 && box.height > 0, 'Card radio has no pointer target.');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const target = await radio.evaluate(element => {
      const rect = element.getBoundingClientRect();
      const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
      const hit = document.elementFromPoint(x, y);
      const buttons = document.querySelectorAll('[data-testid="card-accordion-item-button"]');
      const ownedButton = buttons.length === 1 ? buttons[0] : null;
      return {x, y, allowed: Boolean(hit && (hit === element || element.contains(hit)
        || (ownedButton && (hit === ownedButton || ownedButton.contains(hit)))))};
    });
    assert(target.allowed, 'An unrelated overlay blocks the Card choice.');
    await page.mouse.click(target.x, target.y);
    result.card_action = 'clicked-card-radio-position';
  }
  await number.waitFor({state: 'visible', timeout});
  return result;
}
