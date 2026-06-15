"""Content-variant learning — ties the shared bandit to REAL goals. (Substrate.)

  policy_key:  content::{channel}::{account_id}::{objective}
  arms:        the lens chosen for a piece (from the playbook's target_lens_set)
  reward:      goal_outcome from the playbook's success_metric (not likes)
"""
from __future__ import annotations

from .models import Insight


def policy_key(channel: str, account_id: str, objective: str) -> str:
    return f"content::{channel}::{account_id}::{objective}"


def lens_candidates(target_lens_set: list[str]) -> list[dict]:
    return [{"key": lens, "lens": lens} for lens in target_lens_set]


def features(*, content_kind: str, transcript_len: int, hour_bucket: int,
             day_of_week: int, follower_band: int, recent_reach_avg: float, stakes: str) -> dict:
    stakes_num = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(stakes, 0.0)
    return {
        "is_reel": 1.0 if content_kind == "reel" else 0.0,
        "transcript_len": float(min(transcript_len, 5000)) / 5000.0,
        "hour_bucket": float(hour_bucket) / 23.0,
        "day_of_week": float(day_of_week) / 6.0,
        "follower_band": float(follower_band),
        "recent_reach_avg": float(recent_reach_avg),
        "stakes": stakes_num,
    }


def goal_outcome_from_insight(insight: Insight, success_metric: str, baseline_reach: float = 1.0) -> float:
    baseline = max(baseline_reach, 1.0)
    if success_metric == "reach":
        return float(insight.reach or 0) / baseline
    if success_metric == "saves":
        return float((insight.saves or 0) + (insight.shares or 0)) / baseline
    if success_metric == "leads":
        return float(insight.link_clicks or 0) / baseline
    if success_metric == "follows":
        return float(insight.follows or 0) / baseline
    eng = (insight.saves or 0) + (insight.comments or 0) + (insight.shares or 0)
    return float(eng) / baseline
