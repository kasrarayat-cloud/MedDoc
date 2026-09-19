import assert from 'node:assert/strict';
import {test} from 'node:test';
import {requireExecutionCLI, verificationOutcome} from './stripe_verification_outcome.mjs';

const completed = () => ({mode: 'execute', cases: {
  payment_success: {status: 'passed'}, failed_payment: {status: 'passed'},
  refund: {status: 'passed'},
  duplicate_delivery: {status: 'passed', arrival_confirmed_by_runner: true},
  retry_after_receiver_failure: {status: 'passed', failure_observed: true, redelivery_confirmed: true},
  out_of_order_delivery: {status: 'passed', arrival_order_confirmed: true},
}});

test('execute requires operator CLI before a checkout; dry run does not', () => {
  assert.throws(() => requireExecutionCLI(true, ''), /requires/);
  assert.doesNotThrow(() => requireExecutionCLI(false, ''));
  assert.doesNotThrow(() => requireExecutionCLI(true, '/synthetic/stripe'));
});

test('dry-run readiness is explicitly not sandbox acceptance', () => {
  assert.deepEqual(verificationOutcome({mode: 'dry-run'}),
    {passed: true, sandbox_acceptance: 'not attempted', pending_cases: []});
});

test('old no-CLI false pass remains incomplete', () => {
  const report = completed();
  report.cases.duplicate_delivery = {status: 'skipped'};
  report.cases.refund = {status: 'skipped'};
  report.cases.retry_after_receiver_failure = {status: 'manual'};
  report.cases.out_of_order_delivery = {status: 'manual'};
  const result = verificationOutcome(report);
  assert.equal(result.passed, false);
  assert.equal(result.sandbox_acceptance, 'incomplete');
  assert.deepEqual(result.pending_cases,
    ['refund', 'duplicate_delivery', 'retry_after_receiver_failure', 'out_of_order_delivery']);
});

test('unchanged balance without observed duplicate arrival cannot pass', () => {
  for (const status of ['passed with a stated limit', 'passed']) {
    const report = completed();
    report.cases.duplicate_delivery = {status, arrival_confirmed_by_runner: false};
    assert.deepEqual(verificationOutcome(report).pending_cases, ['duplicate_delivery']);
  }
});

test('retry requires both failed receipt and confirmed redelivery', () => {
  for (const flag of ['failure_observed', 'redelivery_confirmed']) {
    const report = completed();
    delete report.cases.retry_after_receiver_failure[flag];
    assert.deepEqual(verificationOutcome(report).pending_cases, ['retry_after_receiver_failure']);
  }
});

test('out-of-order requires observed arrival order', () => {
  const report = completed();
  delete report.cases.out_of_order_delivery.arrival_order_confirmed;
  assert.deepEqual(verificationOutcome(report).pending_cases, ['out_of_order_delivery']);
});

test('absent required cases fail closed', () => {
  assert.equal(verificationOutcome({mode: 'execute'}).pending_cases.length, 6);
  for (const name of Object.keys(completed().cases)) {
    const report = completed();
    delete report.cases[name];
    assert.deepEqual(verificationOutcome(report).pending_cases, [name]);
  }
});

test('complete synthetic classification fixture can pass; creates no real Stripe evidence', () => {
  assert.deepEqual(verificationOutcome(completed()),
    {passed: true, sandbox_acceptance: 'passed', pending_cases: []});
});
