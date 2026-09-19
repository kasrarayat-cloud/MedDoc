// Evidence classification only. This module performs no network or file access.
export function requireExecutionCLI(execute, stripeCli) {
  if (execute && !stripeCli) throw new Error('Sandbox execution requires the operator Stripe CLI.');
}

const requiredCases = [
  'payment_success', 'failed_payment', 'refund', 'duplicate_delivery',
  'retry_after_receiver_failure', 'out_of_order_delivery',
];

export function verificationOutcome(report) {
  if (report.mode === 'dry-run') {
    return {passed: true, sandbox_acceptance: 'not attempted', pending_cases: []};
  }
  const pending = requiredCases.filter(name => {
    const result = report.cases?.[name];
    if (result?.status !== 'passed') return true;
    if (name === 'duplicate_delivery') return result.arrival_confirmed_by_runner !== true;
    if (name === 'retry_after_receiver_failure') {
      return result.failure_observed !== true || result.redelivery_confirmed !== true;
    }
    if (name === 'out_of_order_delivery') return result.arrival_order_confirmed !== true;
    return false;
  });
  return {passed: pending.length === 0,
    sandbox_acceptance: pending.length ? 'incomplete' : 'passed', pending_cases: pending};
}
