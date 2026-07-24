# VibeSentinel — a smoke detector for your self-hosted server

**For the developer who shipped an app to a VPS and has no idea who's poking at it.**

---

## Who this is for

You run your own stuff on your own box:

- A side project or small SaaS on a $5–40 VPS (Hetzner, DigitalOcean, Vultr, a Pi at home).
- A homelab, an internal tool, a client app you deployed and moved on from.
- You deploy on vibes — ship fast, iterate, no security team behind you.

You are **not** a SOC analyst, you don't have a Datadog budget, and you're not
going to stand up an ELK stack to babysit one server.

## The problem

Your server is on the public internet, which means bots are already hitting it —
probing `/wp-login.php`, trying `' OR 1=1`, scanning for `.env` and `.git/config`,
throwing XSS at every query param. You find out about none of it, because:

- **Raw logs are noise.** Thousands of lines a day; the three that matter are buried.
- **Real security tooling is built for enterprises.** Heavy, expensive, and it ships
  your logs to someone else's cloud.
- **You'd have to become a security person** to configure any of it.

So most self-hosted apps run blind. The first sign of trouble is when something
is already broken.

## What VibeSentinel does

Point it at a project, run your server, and it watches the live log stream and
tells you — in real time — when someone is attacking it.

- **Live attack detection.** SQL injection, XSS, path traversal, command injection,
  recon/scanner probes, and behavioral anomalies (brute force, scanning, traffic
  spikes) — flagged as they happen, not in a weekly report.
- **A two-terminal workspace, zero config.** One terminal runs your server, the
  other runs tests/traffic. A live alert feed sits underneath. Filter to **danger
  only** when you just want the real attacks.
- **A startup scan** that checks for leaked secrets, weak credentials, risky Docker
  settings, and known-vulnerable dependencies *before* traffic hits your app.
- **One dashboard** for every project you're watching, on one port.

## Why it's different

- **100% local. Nothing leaves your box.** The detection model (Drain3 + a small
  ONNX embedding + Isolation Forest) runs on CPU on your own server. **No LLM, no
  API keys, no cloud, no log shipping.** Your logs are yours.
- **Learns your normal.** It seeds from a real traffic baseline and adapts to what
  *your* app's traffic actually looks like, so alerts mean something.
- **Honest signal.** A warmup window and a payload-signature layer keep the
  false-positive rate low — measured **100% attack recall with 0 false positives**
  on the demo run (see [`MODEL_STATS.md`](MODEL_STATS.md)). Alerts you can trust are
  alerts you'll actually read.
- **One command.** `sentinal-core`, open the dashboard, done. Free and open source.

## What it is *not*

Straight talk so you deploy it for the right reasons:

- Not an enterprise SIEM or a compliance product. It's a **smoke detector**, not a
  fire department.
- Not a WAF — it tells you you're being attacked; it doesn't sit inline blocking
  every request (though it can help you ban an attacking IP).
- Not a replacement for patching, good passwords, and a firewall. It's the layer
  that tells you when those aren't enough.

## Try it in two minutes

```bash
pip install -e "./backend[core]"
cd dashboard && npm ci && npm run build
sentinal-core          # open http://localhost:8000
```

Click **Load demo project**, run `python3 /opt/demo_server.py` in one terminal and
`python3 /opt/traffic.py` in the other, and watch real attacks light up the feed.
Then point a project at your own app.

---

_VibeSentinel: because "it's just a small server" is exactly what the bots are
counting on._
