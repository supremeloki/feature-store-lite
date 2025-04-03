from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


class FeatureStoreError(Exception):
    pass


class UnknownFeatureError(FeatureStoreError):
    def __init__(self, feature: str) -> None:
        super().__init__(f"unknown feature: {feature!r}")


class EntityNotFoundError(FeatureStoreError):
    def __init__(self, entity_id: str) -> None:
        super().__init__(f"entity not found: {entity_id!r}")


@dataclass(frozen=True)
class FeatureValue:
    entity_id: str
    feature: str
    value: Any
    timestamp: float
    computed_at_request: bool = False


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    dtype: type
    ttl_seconds: float | None = None
    transformer: Callable[[dict[str, Any]], Any] | None = None

    def __post_init__(self) -> None:
        if self.ttl_seconds is not None and self.ttl_seconds <= 0:
            raise FeatureStoreError("ttl must be positive")


@dataclass(frozen=True)
class FeatureVector:
    entity_id: str
    values: dict[str, Any]
    missing: tuple[str, ...]

    def complete(self) -> bool:
        return not self.missing


class FeatureStore:
    def __init__(self) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}
        self._materialized: dict[str, dict[str, tuple[Any, float]]] = {}

    def define(self, definition: FeatureDefinition) -> "FeatureStore":
        if definition.name in self._definitions and \
                self._definitions[definition.name].dtype != definition.dtype:
            raise FeatureStoreError(
                f"feature {definition.name!r} redefined with different dtype"
            )
        self._definitions[definition.name] = definition
        return self

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def materialize(
        self,
        entity_id: str,
        features: dict[str, Any],
        source_timestamp: float | None = None,
    ) -> int:
        stored_at = source_timestamp if source_timestamp is not None else time.time()
        written = 0
        for name, value in features.items():
            definition = self._require(name)
            if not isinstance(value, definition.dtype):
                raise FeatureStoreError(
                    f"{name!r} expects {definition.dtype.__name__}, got {type(value).__name__}"
                )
            self._materialized.setdefault(entity_id, {})[name] = (value, stored_at)
            written += 1
        return written

    def get_feature(self, entity_id: str, feature: str,
                    now: float | None = None) -> FeatureValue:
        definition = self._require(feature)
        entry = self._materialized.get(entity_id, {}).get(feature)
        reference_now = now if now is not None else time.time()
        if entry is not None:
            value, stored_at = entry
            if definition.ttl_seconds is None or (reference_now - stored_at) < definition.ttl_seconds:
                return FeatureValue(entity_id=entity_id, feature=feature,
                                    value=value, timestamp=stored_at)
            del self._materialized[entity_id][feature]
        computed = self._compute_from_transformer(entity_id, definition)
        return FeatureValue(entity_id=entity_id, feature=feature, value=computed,
                            timestamp=reference_now, computed_at_request=True)

    def get_online_vector(self, entity_id: str, features: Sequence[str],
                          now: float | None = None) -> FeatureVector:
        values: dict[str, Any] = {}
        missing: list[str] = []
        for feature in features:
            try:
                resolved = self.get_feature(entity_id, feature, now=now)
            except FeatureStoreError:
                missing.append(feature)
                continue
            if resolved.computed_at_request and resolved.value is None:
                missing.append(feature)
                continue
            values[feature] = resolved.value
        return FeatureVector(entity_id=entity_id, values=values, missing=tuple(missing))

    def purge_entity(self, entity_id: str) -> int:
        removed = len(self._materialized.pop(entity_id, {}))
        return removed

    def _require(self, feature: str) -> FeatureDefinition:
        definition = self._definitions.get(feature)
        if definition is None:
            raise UnknownFeatureError(feature)
        return definition

    def _compute_from_transformer(self, entity_id: str,
                                  definition: FeatureDefinition) -> Any:
        if definition.transformer is None:
            return None
        row = dict(self._materialized.get(entity_id, {}).items().__iter__().__next__()  # noqa
                   ) if False else {
            name.split(".", 1)[-1]: value
            for name, (value, _) in self._materialized.get(entity_id, {}).items()
        }
        row["entity_id"] = entity_id
        return definition.transformer(row)
