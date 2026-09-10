import prisma from '@meddoc/db';
const ID='9e758c45-ac65-4996-bea8-6fc1f8b1c96c';
(async () => {
  const r = await prisma.templateTwinCompiledVersion.findUnique({
    where:{id:ID},
    select:{ latestTestRoundTrip:true, latestTestOutputSha256:true, latestTestVerifiedAt:true,
             latestTestStaticContentSha256:true, certificationStatus:true },
  });
  const rt = (r?.latestTestRoundTrip ?? null) as any;
  console.log('  verifiedAt        :', r?.latestTestVerifiedAt?.toISOString() ?? '<none>');
  console.log('  outputSha256      :', r?.latestTestOutputSha256?.slice(0,16) ?? '<none>');
  console.log('  certificationStatus:', r?.certificationStatus);
  if (!rt) { console.log('  🔴 no round-trip stored'); return; }
  console.log('  round-trip keys   :', Object.keys(rt).join(', '));
  console.log('  verified          :', rt.verified);
  const fields = (rt.fields ?? rt.fieldProofs ?? []) as Array<Record<string,unknown>>;
  console.log('  proof entries     :', fields.length);
  const byKind: Record<string, number> = {};
  for (const f of fields) byKind[String(f.kind)] = (byKind[String(f.kind)] ?? 0) + 1;
  console.log('  ── PROOF KINDS ──');
  for (const [k,v] of Object.entries(byKind).sort()) console.log(`     ${k.padEnd(12)} ${v}`);
  const body = fields.filter(f => f.partName === 'word/document.xml');
  const bodyKinds: Record<string, number> = {};
  for (const f of body) bodyKinds[String(f.kind)] = (bodyKinds[String(f.kind)] ?? 0) + 1;
  console.log('  ── BODY ONLY (word/document.xml) ──');
  for (const [k,v] of Object.entries(bodyKinds).sort()) console.log(`     ${k.padEnd(12)} ${v}`);
  const emptied = fields.filter(f => f.kind === 'emptied');
  console.log('  emptied WITH expectedSpanSha256:', emptied.filter(f => typeof f.expectedSpanSha256 === 'string' && (f.expectedSpanSha256 as string).length === 64).length, '/', emptied.length);
  await prisma.$disconnect();
})().catch(async e => { console.error('🔴', e?.message ?? e); await prisma.$disconnect(); process.exitCode = 1; });
