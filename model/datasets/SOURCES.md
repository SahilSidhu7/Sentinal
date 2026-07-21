# Dataset Sources

Raw archives and extracted logs are gitignored (not committed) — third-party data, fetch per below. Drop `Apache.tar.gz`, `Linux.tar.gz`, `SSH.tar.gz` in this folder, then run `python scripts/prepare_datasets.py` (or just run `train_baseline.py`, which calls it automatically) to extract them.

## How to obtain

Request access via the loghub repo: https://github.com/logpai/loghub — the README links to a Zenodo/Google-Drive request form gating the actual dataset downloads (loghub gates access to discourage indiscriminate scraping, not because of a paywall).

## In use

All three are from [loghub](https://github.com/logpai/loghub) (LOGPAI), the standard academic corpus for log-anomaly-detection research. Citation: Jieming Zhu et al., "Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics" (ISSRE 2023), https://arxiv.org/abs/2008.06448.

| File | Source | Lines | Content |
|---|---|---|---|
| `Apache.tar.gz` | Apache HTTP error/notice log | ~56.5k | server startup/notice noise + real `[error]` entries (mod_jk failures, `Directory index forbidden`, denied-client entries) |
| `Linux.tar.gz` | Linux syslog (RedHat box, 2005) | ~25.6k | boot/kernel/cron noise + a real sustained SSH brute-force campaign (`authentication failure`, `illegal user`) against `sshd(pam_unix)` |
| `SSH.tar.gz` | OpenSSH auth log, "LabSZ" honeypot | ~655k | internet-facing honeypot under continuous real brute-force attack; known ground truth (per loghub docs): 24 distinct source IPs, 23 malicious / 1 benign |

These give real baseline "normal" traffic (server startup, routine cron/kernel messages, legitimate access) plus real attack traffic (SSH brute force, invalid-user probing, forbidden-directory access) — a solid fit for training/validating the Isolation Forest anomaly path (spec §4) on auth-log and Apache-log sources.

Gap: none of the three contain HTTP-request-line attacks (SQLi/XSS/path-traversal payloads in a URL) — that's covered by `examples/synthetic_logs.py` instead, since no suitable *loggable* public dataset was found without manual registration/licensing steps (see below). Heuristic auth-attack labels are for **evaluation sanity-checking only** — Isolation Forest training itself stays unsupervised (spec §4 step 3), no labels are fed into `train()`.

## Researched, not yet pulled in (need manual fetch / licensing check before use)

Priority order — top one closes the biggest actual gap (real HTTP-attack traffic):

1. **CSIC 2010 HTTP dataset** — 36k normal + 25k+ anomalous labeled HTTP requests against a simulated e-commerce app: SQLi, XSS, buffer overflow, CRLF injection, parameter tampering, path traversal, SSI, files disclosure. This is real request-line attack traffic, not synthetic — directly replaces/validates `examples/synthetic_logs.py`'s SQLi/XSS/traversal generator with ground-truth-labeled data. Original host (`isi.csic.es`) has moved around over the years; current easiest mirror is Kaggle (`ispangler/csic-2010-web-application-attacks`). Manual download (Kaggle auth required) — check the mirror's stated license/terms before committing any of it into this repo.
2. **Morzeux/HttpParamsDataset (GitHub)** — smaller, focused: benign vs. attack payload strings (SQLi, XSS, command injection, path traversal) meant to be dropped into HTTP param values — good as a payload-variety supplement even after CSIC 2010 is in, cheap to template-ify for Drain3 since it's just param strings, not full log lines.
3. **loghub OpenStack** — normal + failure-injected abnormal logs from real OpenStack VM lifecycle ops. Relevant if VibeSentinel targets containerized/virtualized self-hosted infra, not just bare Nginx/SSH boxes.
4. **loghub Windows** — relevant since a meaningful slice of self-hosted-server operators (our target user per spec §1) run Windows Server, not just Linux. Closes a real blind spot — everything currently in `/model` is Linux/Unix-flavored (syslog, SSH, Apache on *nix).
5. **loghub Zookeeper / Hadoop / HDFS** — lower priority for our target user (indie devs / small self-hosted ops), these are distributed-systems-at-scale logs more relevant to teams running that specific stack. Worth adding only if a teammate's target audience actually runs it.
- **AIT-LDS (`ait-aecid/anomaly-detection-log-datasets`, GitHub)** — curated multi-source log anomaly datasets with documented labels; worth a look for additional Apache/auth sources if the loghub three prove insufficient.

Don't add any of these without a licensing check first — the three already in `/model/datasets` are used under loghub's terms for research/education, which is what this is. Kaggle-mirrored datasets in particular: confirm the mirror's own license, not just the original paper's stated terms.
