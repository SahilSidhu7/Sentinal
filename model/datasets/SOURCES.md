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

Heuristic auth-attack labels (for Apache/Linux/SSH) are for **evaluation sanity-checking only** — Isolation Forest training itself stays unsupervised (spec §4 step 3), no labels are fed into `train()`.

## CSIC 2010 HTTP dataset (in use, real labels, ML approach doesn't work on it yet)

36,000 normal + 25,065 real-labeled anomalous HTTP requests against a simulated e-commerce app: SQLi, XSS, buffer overflow, CRLF injection, parameter tampering, path traversal, SSI, files disclosure. Unlike the loghub three, ground truth here is **real** (`norm`/`anom` per request from the dataset itself), not a regex proxy.

**License:** no formal license found from the original rights holder (CSIC — Carmen Torrano Giménez, Alejandro Pérez Villegas, Gonzalo Álvarez Marañón). The original host (`isi.csic.es`) has moved repeatedly; current mirror used is `lexr.ai/csic_dataset/` (maintained by Peter Scully, whose page states informal permission: *"feel free to download and use them as you see fit"*, requesting attribution to the original CSIC researchers). This is a mirror maintainer's informal blessing, **not** a stated open license from CSIC. Treated the same as the loghub datasets: fine for local research/training use, kept **gitignored** (`csic2010_full.csv.zip`, `_extracted/CSIC2010/`), never committed to this public repo.

**How to obtain:** `curl -o model/datasets/csic2010_full.csv.zip http://lexr.ai/csic_dataset/output_http_csic_2010_weka_with_duplications_RAW-RFC2616_escd_v02_full.csv.zip` — `scripts/csic_dataset.py` extracts and reconstructs full-request log lines from it automatically (the CSV is one row per request *parameter*, grouped by an `index` column — reconstruction verified against the dataset's published stats, 36k/25k).

**Status:** loader works, but the Drain3+MiniLM+IsolationForest pipeline doesn't separate normal from attack traffic on this dataset (~50-95% FP depending on threshold — see `model/README.md` "Known limitation 2" for the diagnosis and why this points to a signature/regex pre-filter, not more ML tuning, as the fix). Not wired into `train_baseline.py`'s default run — use `--with-csic` to include it.

## Other datasets researched, not pulled in

1. **Morzeux/HttpParamsDataset (GitHub)** — smaller, focused: benign vs. attack payload strings (SQLi, XSS, command injection, path traversal) meant to be dropped into HTTP param values. Good fit for a future signature/regex pre-filter's test fixtures (see CSIC2010 status above), not for this package's embedding approach.
2. **loghub OpenStack** — normal + failure-injected abnormal logs from real OpenStack VM lifecycle ops. Relevant if VibeSentinel targets containerized/virtualized self-hosted infra, not just bare Nginx/SSH boxes.
3. **loghub Windows** — relevant since a meaningful slice of self-hosted-server operators (our target user per spec §1) run Windows Server, not just Linux. Closes a real blind spot — everything currently in `/model` is Linux/Unix-flavored.
4. **loghub Zookeeper / Hadoop / HDFS** — lower priority for our target user (indie devs / small self-hosted ops); distributed-systems-at-scale logs more relevant to teams running that specific stack.
5. **AIT-LDS (`ait-aecid/anomaly-detection-log-datasets`, GitHub)** — curated multi-source log anomaly datasets with documented labels; worth a look for additional Apache/auth sources if the loghub three prove insufficient.

Don't add any of these without a licensing check first — same posture as loghub/CSIC2010: local research/training use only, gitignored, never committed.
