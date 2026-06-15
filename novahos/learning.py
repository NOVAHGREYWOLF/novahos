"""Per-user contextual bandit (River). Shared by every app. (Substrate.)

Reward is whatever the caller computes — for content it's the goal_outcome from a playbook's
success_metric (see content_learning), never vanity likes. Policy pickled to bandit_state,
partitioned by user_id + policy_key.
"""
import pickle

from river import linear_model, preprocessing
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BanditState, Suggestion, SuggestionOutcome

EPSILON = 0.10
WARM_OBS = 5
PRIOR_MIN_CONFIDENCE = 0.70


def _new_arm():
    return preprocessing.StandardScaler() | linear_model.LinearRegression()


class Policy:
    def __init__(self) -> None:
        self.arms: dict[str, object] = {}
        self.counts: dict[str, int] = {}

    def ensure(self, action_key: str) -> None:
        if action_key not in self.arms:
            self.arms[action_key] = _new_arm()
            self.counts[action_key] = 0

    def predict(self, action_key: str, features: dict) -> float:
        self.ensure(action_key)
        return float(self.arms[action_key].predict_one(features) or 0.0)

    def learn(self, action_key: str, features: dict, reward: float) -> None:
        self.ensure(action_key)
        self.arms[action_key].learn_one(features, reward)
        self.counts[action_key] += 1

    def min_count(self) -> int:
        return min(self.counts.values()) if self.counts else 0


async def _load(db: AsyncSession, user_id: str, policy_key: str) -> tuple[Policy, BanditState | None]:
    row = (await db.execute(
        select(BanditState).where(BanditState.user_id == user_id, BanditState.policy_key == policy_key)
    )).scalar_one_or_none()
    if row is None:
        return Policy(), None
    return pickle.loads(row.model), row


async def _save(db: AsyncSession, user_id: str, policy_key: str, policy: Policy, row: BanditState | None) -> None:
    blob = pickle.dumps(policy)
    if row is None:
        db.add(BanditState(user_id=user_id, policy_key=policy_key, model=blob))
    else:
        row.model = blob


def _seed(rng_seed: int) -> float:
    x = (rng_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return x / 0x7FFFFFFF


async def choose(
    db: AsyncSession,
    user_id: str,
    features: dict,
    candidates: list[dict],
    prior_scores: dict[str, float] | None = None,
    prior_confidence: float = 1.0,
    policy_key: str = "daily_action_selector",
    decision_seed: int = 0,
) -> tuple[dict, float, str]:
    policy, row = await _load(db, user_id, policy_key)
    keys = [c["key"] for c in candidates]
    for k in keys:
        policy.ensure(k)

    cold = policy.min_count() < WARM_OBS
    use_prior = cold and prior_scores is not None and prior_confidence >= PRIOR_MIN_CONFIDENCE

    if use_prior:
        scores = {k: prior_scores.get(k, 0.0) for k in keys}
        source = "llm_prior"
    else:
        scores = {k: policy.predict(k, features) for k in keys}
        source = "bandit"

    k = len(keys)
    explore = _seed(decision_seed) < EPSILON
    if explore or (cold and not use_prior):
        idx = int(_seed(decision_seed + 1) * k) % k
        chosen_key = keys[idx]
        prob = EPSILON / k
        source = "explore"
    else:
        chosen_key = max(scores, key=scores.get)
        prob = 1 - EPSILON + EPSILON / k

    await _save(db, user_id, policy_key, policy, row)
    action = next(c for c in candidates if c["key"] == chosen_key)

    sug = Suggestion(user_id=user_id, context=features, action=action, source=source, prob=prob)
    db.add(sug)
    await db.flush()
    action = {**action, "_suggestion_id": sug.id}
    return action, prob, source


async def record_outcome(
    db: AsyncSession,
    user_id: str,
    suggestion_id: str,
    reward: float,
    policy_key: str = "daily_action_selector",
) -> None:
    sug = (await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))).scalar_one_or_none()
    if sug is None:
        return
    db.add(SuggestionOutcome(suggestion_id=suggestion_id, user_id=user_id, reward=reward))
    policy, row = await _load(db, user_id, policy_key)
    policy.learn(sug.action["key"], sug.context, reward)
    await _save(db, user_id, policy_key, policy, row)
