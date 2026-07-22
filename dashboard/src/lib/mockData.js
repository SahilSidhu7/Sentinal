// Mock data shaped per docs/SPEC.md §5 (findings/attack_events/score) so
// swapping in /cli's real local feed later is minimal rework. Used as a
// fallback in api.js when /cli isn't reachable.

export const mockScore = {
  score: 98,
  issues_open: 2,
  metrics: [
    { key: 'latency', label: 'System Latency', value: 12, unit: 'ms', pct: 12 },
    { key: 'encryption_load', label: 'Encryption Load', value: 42, unit: '%', pct: 42 },
  ],
}

export const mockFindings = [
  {
    id: 'f-1',
    type: 'log_anomaly',
    severity: 'high',
    title: 'Unusual access pattern detected from Frankfurt',
    description: 'Node-X7 experienced 40+ failed auth attempts in 3 minutes.',
    status: 'open',
    detected_at: '2026-07-21T14:02:00Z',
  },
  {
    id: 'f-2',
    type: 'dependency_cve',
    severity: 'medium',
    title: 'Outdated SSL certificate in Sandbox B',
    description: 'Certificate expires in 48 hours. Auto-renewal failed.',
    status: 'open',
    detected_at: '2026-07-21T13:40:00Z',
  },
  {
    id: 'f-3',
    type: 'fim',
    severity: 'safe',
    title: 'Database snapshots verified',
    description: 'Daily integrity check completed successfully for all clusters.',
    status: 'resolved',
    detected_at: '2026-07-21T12:00:00Z',
  },
]

export const mockAttackEvents = [
  {
    id: 'a-1',
    source_ip: '192.168.1.45',
    attack_type_guess: null,
    confidence: null,
    message: 'User Admin accessed /settings',
    actor: 'Admin',
    kind: 'auth',
    detected_at: '2026-07-21T14:15:00Z',
  },
  {
    id: 'a-2',
    source_ip: null,
    attack_type_guess: 'brute_force',
    confidence: 0.87,
    message: 'Multiple failed login attempts from Unknown Source',
    actor: 'Unknown Source',
    kind: 'warning',
    region: 'EU-West-1',
    detected_at: '2026-07-21T14:12:00Z',
  },
  {
    id: 'a-3',
    source_ip: null,
    attack_type_guess: null,
    confidence: null,
    message: 'System automated backup completed successfully',
    actor: 'System',
    kind: 'neutral',
    size: '4.2GB',
    detected_at: '2026-07-21T14:00:00Z',
  },
  {
    id: 'a-4',
    source_ip: null,
    attack_type_guess: null,
    confidence: null,
    message: 'API Key Sentinel-X refreshed for node 09',
    actor: 'System',
    kind: 'success',
    node: 'Tokyo-09',
    detected_at: '2026-07-21T13:45:00Z',
  },
  {
    id: 'a-5',
    source_ip: null,
    attack_type_guess: 'unrecognized_process',
    confidence: 0.72,
    message: 'Unrecognized container temp-worker-33 spawned',
    actor: 'temp-worker-33',
    kind: 'warning',
    image: 'unknown:latest',
    detected_at: '2026-07-21T13:30:00Z',
  },
]

export const mockActivityTemplates = [
  { actor: 'System', message: 'performed weekly core audit', target: 'fs-root', kind: 'neutral', icon: 'terminal' },
  { actor: 'Dev-Ops', message: 'pushed new build', target: 'cluster-A4', kind: 'success', icon: 'upload' },
  { actor: 'SecurityBot', message: 'detected anomalous traffic', target: 'Port 443', kind: 'warning', icon: 'security' },
  { actor: 'User-02', message: 'requested password reset', target: 'Auth-Layer', kind: 'neutral', icon: 'lock_reset' },
]

// NOTE: Containers Management has no corresponding table/endpoint in
// docs/SPEC.md §5/§6 (only findings/attack_events/bans/audit_log are
// defined there). This mock module intentionally has no matching entry in
// api.js's real-fetch path — it's presentation-only until a contract exists.
export const mockContainers = [
  {
    id: '4f92bc8102',
    name: 'auth-service-v2',
    status: 'running',
    image: 'sentinel/auth:stable',
    uptime: '14d 02h 12m',
    cpu_pct: 65,
  },
  {
    id: '88a12e34ff',
    name: 'api-gateway-node-01',
    status: 'running',
    image: 'sentinel/gateway:3.1',
    uptime: '06d 18h 44m',
    cpu_pct: 28,
  },
  {
    id: '2c19e09d11',
    name: 'data-ingest-worker',
    status: 'stopped',
    image: 'sentinel/ingest:v1.2',
    exit_info: 'Exited (0) 2h ago',
    cpu_pct: 0,
  },
  {
    id: 'f09231aa4e',
    name: 'db-primary-replica',
    status: 'error',
    image: 'postgres:15-alpine',
    exit_info: '137 (OOM)',
    cpu_pct: 100,
  },
  {
    id: '33b889c101',
    name: 'redis-cache-layer',
    status: 'running',
    image: 'redis:7-alpine',
    uptime: '42d 11h 09m',
    cpu_pct: 12,
  },
]

export const mockSettings = {
  operator_name: 'Cmdr. Sterling',
  email: 'sterling@sentinel.security',
  department: 'Cyber-Defense Intelligence',
  two_factor_enabled: true,
  session_timeout_enabled: true,
  ip_whitelist: '',
  notify_critical_alerts: true,
  notify_log_summaries: true,
  notify_marketing: false,
}
