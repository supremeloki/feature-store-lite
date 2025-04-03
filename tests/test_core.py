import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from feature_store import (
    FeatureDefinition,
    FeatureStore,
    FeatureStoreError,
    UnknownFeatureError,
)


@pytest.fixture
def store():
    app = FeatureStore()
    app.define(FeatureDefinition(name="age", dtype=int))
    app.define(FeatureDefinition(name="balance", dtype=float))
    return app


def test_define_and_materialize(store):
    written = store.materialize("u1", {"age": 30, "balance": 120.5})
    assert written == 2
    vector = store.get_online_vector("u1", ["age", "balance"])
    assert vector.complete()
    assert vector.values["age"] == 30


def test_dtype_enforced(store):
    with pytest.raises(FeatureStoreError):
        store.materialize("u2", {"age": "thirty"})


def test_redefinition_same_dtype_ok_different_dtype_rejected():
    app = FeatureStore()
    app.define(FeatureDefinition("f", int))
    app.define(FeatureDefinition("f", int))
    with pytest.raises(FeatureStoreError):
        app.define(FeatureDefinition("f", str))


def test_unknown_feature_rejected_on_get(store):
    with pytest.raises(UnknownFeatureError):
        store.get_feature("u1", "ghost")


def test_unknown_feature_in_vector_goes_missing(store):
    store.materialize("u3", {"age": 40})
    vector = store.get_online_vector("u3", ["age", "unknown_feature"])
    assert not vector.complete()
    assert vector.missing == ("unknown_feature",)


def test_ttl_expiry_forces_missing(store):
    class Clock:
        now = 1000.0
        def __call__(self):
            return self.now

    clock = Clock()
    app = FeatureStore()
    app.define(FeatureDefinition("score", float, ttl_seconds=10.0))
    import feature_store.core as core
    original_time = __import__("time").time
    __import__("time").time = lambda: clock.now
    try:
        app.materialize("e", {"score": 0.9})
        fresh = app.get_feature("e", "score")
        assert fresh.value == 0.9
    finally:
        __import__("time").time = original_time
    # simulate expiry via direct lookup with future `now`
    stale = app.get_online_vector("e", ["score"], now=2000.0)
    assert "score" in stale.missing


def test_transformer_computes_on_demand():
    app = FeatureStore()
    app.define(FeatureDefinition(name="balance", dtype=float))
    app.define(FeatureDefinition(
        name="double_balance", dtype=float,
        transformer=lambda row: row.get("balance", 0.0) * 2,
    ))
    app.materialize("acct", {"balance": 50.0})
    value = app.get_feature("acct", "double_balance")
    assert value.value == 100.0
    assert value.computed_at_request is True


def test_purge_entity_removes_all_features(store):
    store.materialize("gone", {"age": 1, "balance": 2.0})
    removed = store.purge_entity("gone")
    assert removed == 2
    vector = store.get_online_vector("gone", ["age"])
    assert "age" in vector.missing


def test_negative_ttl_rejected():
    with pytest.raises(FeatureStoreError):
        FeatureDefinition(name="bad", dtype=int, ttl_seconds=-5)


def test_feature_names_sorted():
    app = FeatureStore()
    app.define(FeatureDefinition("zeta", int))
    app.define(FeatureDefinition("alpha", int))
    assert app.feature_names == ("alpha", "zeta")
