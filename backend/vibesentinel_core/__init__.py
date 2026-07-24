"""vibesentinel_core: the hosted management backend (post-pivot core).

Each *project* is an isolated Linux container ("environment") the user drives
through two browser terminals: one to run their server, one to run tests and
watch live monitoring alerts. The server terminal's output is teed into
/model's LogPipeline so the anomaly detector watches the environment's live
logs in real time — no separate agent, no raw logs leaving the box.
"""

__version__ = "0.3.2"
