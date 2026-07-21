// Sample data matching the shared findings/attack-event shape (docs/SPEC.md
// §5, §6), used while /cli's local feed isn't available yet. Delete/replace
// per-field once Team B confirms the real contract.

export const mockScore = {
  score: 78,
  history: [
    { t: '10:00', score: 91 },
    { t: '11:00', score: 88 },
    { t: '12:00', score: 85 },
    { t: '13:00', score: 80 },
    { t: '14:00', score: 78 },
  ],
}

export const mockFindings = [
  {
    id: 'f-1',
    type: 'secret',
    severity: 'critical',
    title: 'AWS access key committed',
    snippet: 'AKIA************',
    file: 'infra/deploy.sh',
    detected_at: '2026-07-21T13:42:00Z',
    status: 'open',
    explanation: 'A static AWS access key was found in a tracked file.',
    suggested_fix: 'Revoke the key in IAM and load credentials from env/secrets manager instead.',
  },
  {
    id: 'f-2',
    type: 'dependency_cve',
    severity: 'high',
    title: 'lodash <4.17.21 — prototype pollution',
    snippet: 'lodash@4.17.15',
    file: 'package-lock.json',
    detected_at: '2026-07-21T12:10:00Z',
    status: 'open',
    explanation: 'Known CVE affecting the pinned lodash version.',
    suggested_fix: 'Upgrade to lodash@4.17.21 or later.',
  },
  {
    id: 'f-3',
    type: 'fim',
    severity: 'medium',
    title: '.env modified outside deploy window',
    snippet: '.env',
    file: '.env',
    detected_at: '2026-07-21T11:55:00Z',
    status: 'dismissed',
    explanation: 'A critical-file baseline hash changed.',
    suggested_fix: 'Confirm the change was intentional; rotate any secrets it touched.',
  },
]

export const mockAttacks = [
  {
    id: 'a-1',
    source_ip: '203.0.113.42',
    attack_type_guess: 'brute_force',
    confidence: 0.91,
    detected_at: '2026-07-21T14:02:00Z',
    status: 'active',
  },
  {
    id: 'a-2',
    source_ip: '198.51.100.7',
    attack_type_guess: 'sqli',
    confidence: 0.64,
    detected_at: '2026-07-21T13:20:00Z',
    status: 'active',
  },
]

export const mockBans = [
  {
    ip: '203.0.113.42',
    mode: 'manual',
    ttl_expires_at: '2026-07-21T20:02:00Z',
    reversed_at: null,
  },
]
