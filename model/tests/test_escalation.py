from vibesentinel_model.anomaly import DetectionResult
from vibesentinel_model.escalation import EscalationTracker, extract_source_ip, suggest_action


def _hit(severity: float) -> DetectionResult:
    return DetectionResult(template="<IP> Invalid user <*>", flag=-1, severity_score=severity)


def test_extract_source_ip_finds_ipv4():
    assert extract_source_ip('203.0.113.7 - - "GET / HTTP/1.1" 200') == "203.0.113.7"


def test_extract_source_ip_none_when_absent():
    assert extract_source_ip("no ip in this line") is None


def test_single_hit_never_escalates():
    tracker = EscalationTracker(min_events=4)
    assert tracker.observe("203.0.113.7", _hit(0.9), timestamp=0) is None
    assert tracker.observe("203.0.113.7", _hit(0.9), timestamp=1) is None


def test_sustained_hits_from_same_ip_escalate():
    tracker = EscalationTracker(min_events=4, window_seconds=300)
    event = None
    for t in range(4):
        event = tracker.observe("203.0.113.7", _hit(0.8), timestamp=t)
    assert event is not None
    assert event.source_ip == "203.0.113.7"
    assert event.event_count == 4


def test_low_severity_never_counts_toward_escalation():
    tracker = EscalationTracker(min_events=2, severity_threshold=0.6)
    assert tracker.observe("203.0.113.7", _hit(0.3), timestamp=0) is None
    assert tracker.observe("203.0.113.7", _hit(0.3), timestamp=1) is None


def test_gating_is_by_severity_not_raw_flag():
    """flag is contamination-threshold-derived and easy to miscalibrate on a
    small baseline (see model/README.md eval notes) — severity_score is the
    real gate, regardless of what flag says."""
    tracker = EscalationTracker(min_events=1, severity_threshold=0.6)
    high_severity_but_flag_normal = DetectionResult(template="x", flag=1, severity_score=0.9)
    assert tracker.observe("203.0.113.7", high_severity_but_flag_normal, timestamp=0) is not None


def test_window_eviction_resets_count():
    tracker = EscalationTracker(min_events=3, window_seconds=10)
    tracker.observe("203.0.113.7", _hit(0.8), timestamp=0)
    tracker.observe("203.0.113.7", _hit(0.8), timestamp=1)
    # third hit arrives long after window expired -> first two evicted, count restarts
    event = tracker.observe("203.0.113.7", _hit(0.8), timestamp=100)
    assert event is None


def test_different_ips_tracked_independently():
    tracker = EscalationTracker(min_events=2)
    tracker.observe("203.0.113.7", _hit(0.8), timestamp=0)
    event = tracker.observe("203.0.113.8", _hit(0.8), timestamp=0)
    assert event is None  # each IP needs its own 2 hits


def test_suggest_action_ladder():
    assert suggest_action(confidence=0.9, event_count=12) == "ban_ip"
    assert suggest_action(confidence=0.75, event_count=7) == "rate_limit_and_challenge"
    assert suggest_action(confidence=0.65, event_count=1) == "flag_for_review"
    assert suggest_action(confidence=0.3, event_count=1) == "log_only"
