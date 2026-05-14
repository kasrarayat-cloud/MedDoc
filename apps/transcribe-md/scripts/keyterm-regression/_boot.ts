// Side-effect boot: loads /opt/meddoc-pro/.env BEFORE the other imports
// in run.ts. Without this, @meddoc/db's Prisma client initializes with
// no DATABASE_URL and emits SCRAM-SERVER-FIRST-MESSAGE errors on every
// telemetry write (api-usage / AiCall). The errors are harmless (the
// regression run doesn't depend on the telemetry side-channel) but
// noisy in stderr. Importing this file first quiets them.
import { config } from 'dotenv';

config({ path: '/opt/meddoc-pro/.env' });
