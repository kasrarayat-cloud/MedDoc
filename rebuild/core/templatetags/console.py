"""Display helpers for the administration console. No queries, no side effects."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def exact_amount(value):
    """Exact USD text: never rounded, never scientific, always at least two decimals.

    Money is stored as DecimalField(max_digits=24, decimal_places=12). Two renderings were
    previously in use and both misreport it:

      * ``floatformat:6`` ROUNDS. A real balance of 0.000000499999 renders '0.000000' — a nonzero
        balance shown as nothing — and 0.000000999999 renders '0.000001', which is MORE money than
        the account holds. A displayed balance must never exceed the real one.
      * the bare ``{{ value }}`` prints all twelve stored places ('10.000000000000') and does it
        inconsistently, because Decimal keeps the exponent it was constructed with ('1234.5').

    This truncates nothing and invents nothing: it prints every significant place that exists and
    pads to cents when there are fewer. ``format(..., 'f')`` is required — ``str(Decimal('0E-12'))``
    is the scientific '0E-12'.
    """
    if value is None or value == '':
        return ''
    try:
        amount = Decimal(value)
    except (TypeError, ValueError, ArithmeticError, InvalidOperation):
        return ''
    if not amount.is_finite():
        return ''
    whole, _, fraction = format(amount, 'f').partition('.')
    return whole + '.' + fraction.rstrip('0').ljust(2, '0')


@register.filter(name='usd')
def usd(value):
    """'$' + exact_amount, or an explicit em dash when there is no figure to show.

    The minus sign goes OUTSIDE the currency symbol: '-$3.50', never '$-3.50'.
    """
    text = exact_amount(value)
    if not text:
        return '—'
    return ('-$' + text[1:]) if text.startswith('-') else ('$' + text)


@register.filter(name='usd_signed')
def usd_signed(value):
    """Ledger movements read better with an explicit '+' on a credit."""
    text = exact_amount(value)
    if not text:
        return '—'
    return ('+$' + text) if not text.startswith('-') else ('-$' + text[1:])


@register.filter(name='get_item')
def get_item(mapping, key):
    """Dict lookup by a non-literal key. Django's template language has no syntax for it."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter(name='net_cents')
def net_cents(payment, refunded):
    """A payment's amount after succeeded refunds, so a refunded payment cannot read as 'paid'."""
    try:
        return int(payment.amount_cents) - int((refunded or {}).get(payment.pk) or 0)
    except (AttributeError, TypeError, ValueError):
        return None


@register.filter(name='cents_usd')
def cents_usd(value):
    """Stripe amounts are integer cents; the console printed them as bare '1000 ¢'."""
    if value is None or value == '':
        return '—'
    try:
        # Reuse the filter that owns the sign rule, so '$-5.00' and '-$5.00' cannot diverge.
        return usd(Decimal(int(value)) / 100)
    except (TypeError, ValueError, ArithmeticError, InvalidOperation):
        return '—'
