# QuillMD V1 production cost estimate (AWS us-east-1)

Prepared 2026-09-27 for the architecture in `production-hosting.md`. **Nothing is provisioned and
nothing here is a commitment.** All AWS unit prices are us-east-1, on-demand, Linux, read on
2026-09-27 from the pricing data behind aws.amazon.com (EC2 file published 2026-09-25T17:45:21Z,
RDS 2026-09-24T21:10:11Z) by the hosting investigation; a month is 730 hours. Prices not in that
verified set are listed separately as **unverified allowances** and are not in the totals. Taxes,
AWS Support plans and payment-processing fees are excluded.

## 1. Verified unit prices used

| Item | Unit price |
| --- | --- |
| EC2 t3.large / m7i.large / m7i.xlarge | $0.0832 / $0.1008 / $0.2016 per hour ($60.74 / $73.58 / $147.17 per month) |
| T3 unlimited CPU surplus | $0.05 per vCPU-hour |
| EBS gp3 | $0.08 per GB-month (3,000 IOPS and 125 MB/s included) |
| EBS snapshots (standard) / AWS Backup EBS warm | $0.05 per GB-month |
| RDS PostgreSQL db.t4g.medium | $0.065 Single-AZ / $0.129 Multi-AZ per hour ($47.45 / $94.17) |
| RDS PostgreSQL db.t4g.large | $0.129 / $0.258 per hour ($94.17 / $188.34) |
| RDS gp3 storage | $0.115 Single-AZ / $0.23 Multi-AZ per GB-month |
| RDS backup storage | free up to 100% of provisioned storage; then $0.095 per GiB-month |
| AWS Backup RDS snapshot | $0.095 per GB-month |
| RDS T4g CPU credits | $0.075 per vCPU-hour of surplus |
| S3 Standard | $0.023 per GB-month; PUT $0.005 and GET $0.0004 per 1,000 |
| Application Load Balancer | $0.0225 per hour ($16.43/month) + $0.008 per LCU-hour ($5.84 per LCU-month) |
| Public IPv4 address | $0.005 per hour ($3.65/month), in use or idle |
| Data transfer out to the Internet | first 100 GB/month free, then $0.09 per GB |
| NAT gateway (not used) | $0.045 per hour ($32.85/month) + $0.045 per GB |
| KMS | $1 per key-month; $0.03 per 10,000 requests; 20,000 requests/month free |
| Secrets Manager | $0.40 per secret-month; $0.05 per 10,000 API calls |
| CloudWatch Logs | $0.50 per GB ingested; $0.03 per GB-month stored |
| CloudWatch alarms (standard) | $0.10 per alarm metric-month; 10 free |
| Route 53 | $0.50 per hosted zone-month; $0.40 per million standard queries |

## 2. Monthly infrastructure estimate

Volumes follow the capacity assumptions in `production-hosting.md` section 3 (low about 800,
expected about 3,300, high about 11,000 encounters a month).

| Line | Low | Expected | High |
| --- | ---: | ---: | ---: |
| EC2 instance | t3.large $60.74 | m7i.large $73.58 | m7i.xlarge $147.17 |
| EBS gp3 root 30 GB | $2.40 | $2.40 | $2.40 |
| EBS gp3 state volume | 50 GB $4.00 | 100 GB $8.00 | 250 GB $20.00 |
| AWS Backup, EBS state snapshots (warm, incremental) | ~15 GB-mo $0.75 | ~40 GB-mo $2.00 | ~150 GB-mo $7.50 |
| Cross-account copy of the EBS snapshots | $0.75 | $2.00 | $7.50 |
| RDS instance | t4g.medium Single-AZ $47.45 | t4g.medium Single-AZ $47.45 | t4g.large Multi-AZ $188.34 |
| RDS gp3 storage | 20 GB $2.30 | 20 GB $2.30 | 50 GB Multi-AZ $11.50 |
| RDS automated backups / PITR | $0 (within free) | $0 (within free) | ~20 GiB beyond free $1.90 |
| AWS Backup RDS snapshots + cross-account copy | ~2 GB $0.38 | ~5 GB $0.95 | ~20 GB $3.80 |
| ALB hours | $16.43 | $16.43 | $16.43 |
| ALB LCUs | ~0.1 $0.58 | ~1 $5.84 | ~3 $17.52 |
| Public IPv4, ALB (two addresses) | $7.30 | $7.30 | $7.30 |
| Public IPv4, instance (egress, no NAT) | $3.65 | $3.65 | $3.65 |
| KMS: three customer keys | $3.00 | $3.00 | $3.00 |
| KMS requests | $0 (free tier) | $0 (free tier) | ~100,000 $0.24 |
| Secrets Manager: four secrets | $1.60 | $1.60 | $1.60 |
| CloudWatch alarms | ~12 metrics $0.20 | ~20 metrics $1.00 | ~30 metrics $2.00 |
| CloudWatch Logs (AWS service logs only) | ~1 GB $0.50 | ~2 GB + 5 GB stored $1.15 | ~5 GB + 20 GB stored $3.10 |
| S3 Standard (artifacts, CloudTrail, logical backups) | ~2 GB $0.05 | ~30 GB $0.69 | ~150 GB $3.45 |
| Route 53 hosted zone | $0 (DNS stays at the provider) | $0 | $0.50 (if moved) |
| Data transfer out | $0 (under 100 GB) | $0 (under 100 GB) | ~50 GB over $4.50 |
| **Total (verified prices)** | **$152.08** | **$179.34** | **$453.40** |

**Unverified allowances (not in the totals; confirm on the pricing pages before relying on them):**
AWS WAF web ACL with three managed/rate rules (about $8 to $10), GuardDuty (about $1 to $5 at this
volume), AWS Config with a small rule set (about $2 to $5), CloudWatch custom metrics from the agent
(about seven metrics, about $2), Route 53 health check (under $1), SNS email (free tier at this
volume), CloudTrail first management trail (no charge), Session Manager (no additional charge), ACM
public certificate on the ALB (no charge), Healthchecks.io (free tier). Allow about **$15 to $25 per
month** for these. An AWS Support plan, if chosen, is extra.

**What the choices cost.** Load balancer instead of Let's Encrypt on the host: about $29.57/month
expected (hours, one LCU, two addresses). Multi-AZ database: +$46.72/month instance and +$2.30
storage at t4g.medium. RDS instead of a container on the host: $49.75/month expected, which also buys
the five-minute recovery point and removes Docker from the host. Avoiding the NAT gateway saves
$32.85/month plus $0.045/GB.

## 3. Per-encounter provider costs (variable, passed through at 1.5x)

**Claude Sonnet 5** (`claude-sonnet-5`): $2 per million input tokens, $10 per million output tokens
(verified by the model investigation from platform.claude.com on 2026-09-27). Its tokenizer produces
about 30% more tokens than Sonnet 4.6 for the same text; if the workspace uses US-only inference
(`inference_geo`), every token costs 1.1x (whether it does is unknown). The application's own bound
for a form generation is (request bytes + 12,000) input tokens plus 6,000 output tokens
(`core/generation.py`), so a 20,000-byte request is bounded at $0.10.

| Generation | Input tokens | Output tokens | Cost |
| --- | ---: | ---: | ---: |
| Low (short typed note, small form) | 6,000 | 1,500 | $0.027 |
| Expected (8-minute visit, typical form) | 12,000 | 3,000 | $0.054 |
| High (narrative form, 12,000-token output, one repeat) | 2 x 25,000 | 2 x 12,000 | $0.340 |

These token counts are estimates, not measurements: Sonnet 5 has not been run on the production
workload. Re-baseline on the synthetic set before paid use, as the model migration plan requires.

**Deepgram nova-3-medical.** deepgram.com/pricing, fetched with WebFetch on 2026-09-27, lists
pre-recorded **Nova-3 (Monolingual) at $0.0043/min Pay As You Go and $0.0036/min Growth** (Growth
requires "$4K+/year"); it does **not** list Nova-3 Medical separately, and it states "We sign Business
Associate Agreements (BAA) for Enterprise customers handling electronic Protected Health Information
(ePHI)". So the price that will apply under a BAA is an Enterprise contract price, **unknown** until
the owner negotiates it. The estimate uses $0.0043/min, the rate the application already applies
(`cost-definition.md`).

| Voice | Minutes | Cost at $0.0043/min |
| --- | ---: | ---: |
| Low | 4 | $0.017 |
| Expected | 8 | $0.034 |
| High | 20 | $0.086 |

**Per encounter (expected):** typed $0.054 provider cost, $0.081 charged; voice $0.088 provider cost,
$0.133 charged (1.5x, `cost-definition.md`).

**Per month (70% voice, expected mix):** low about 800 encounters → $62 provider cost ($94 charged);
expected about 3,300 → $258 ($387 charged); high about 11,000 → $859 ($1,288 charged). Provider cost
is recovered from doctors' wallets by the existing billing rules; infrastructure is fixed overhead
(`PlatformCost`, never charged to users).

## 4. What a Savings Plan or reservation would change (not a commitment)

AWS states Compute Savings Plans "reduce your costs by up to 66%" and EC2 Instance Savings Plans "up
to 72%" (maximum rates are three-year terms); RDS for PostgreSQL may use Database Savings Plans or
one-year/three-year Reserved Instances (No/Partial/All Upfront). The actual one-year rates for
`m7i.large` and `db.t4g.medium` were **not verified** here.

- Only the instance hours move: $73.58 (EC2) and $47.45 (RDS) of the $179.34 expected total. ALB,
  EBS, public IPv4, KMS, Secrets Manager, backups and data transfer are unaffected.
- Savings = hourly on-demand x 730 x discount. At an illustrative one-year discount of 25% to 35%,
  EC2 would save about $18 to $26 and RDS about $12 to $17 per month, so roughly $30 to $43 on the
  expected total. CPU credits for T-class instances are not covered by reservations.
- Recommended: run on-demand for 60 to 90 days, measure, then decide. Committing is an owner decision
  (money).
