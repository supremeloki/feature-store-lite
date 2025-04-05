# feature-store-lite

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A minimal feature store: typed feature definitions, entity-keyed materialization with TTL freshness, on-demand transformers, and online vector assembly — Feast's core ideas in one dependency-free package.

## 🚀 Overview

Serving stale or type-wrong features silently poisons models. `feature-store-lite` declares each feature once (`FeatureDefinition(name, dtype, ttl)`), enforces dtypes at materialization time, expires entries past their TTL on lookup, and assembles **online vectors** for an entity — explicitly listing which features are missing instead of filling silent zeros. Optional transformers compute derived features on demand from already-materialized values.

## ✨ Features

- **Typed definitions:** dtype enforced per feature; conflicting redefinitions rejected
- **TTL freshness:** expired materialized values deleted lazily; injectable `now` for tests
- **On-demand features:** `transformer` callables compute derived values from stored rows
- **Online vectors:** multi-feature fetch returning `{values, missing}` — no silent defaults
- **Entity isolation:** purge a single entity without touching others
- **Zero dependencies**

## 🚧 Structure

```
feature-store-lite/
├── src/feature_store/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── test_core.py
├── README.md
└── pyproject.toml
```

## 📦 Installation

```bash
git clone https://github.com/supremeloki/feature-store-lite.git
cd feature-store-lite
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 📋 Requirements

- Python 3.11+
- No runtime dependencies

## 🏃 Quick Start

```python
from feature_store import FeatureDefinition, FeatureStore

store = (
    FeatureStore()
    .define(FeatureDefinition(name="age", dtype=int))
    .define(FeatureDefinition(name="balance", dtype=float))
    .define(FeatureDefinition(
        name="double_balance", dtype=float,
        transformer=lambda row: row.get("balance", 0.0) * 2,
    ))
)

store.materialize("acct:1", {"age": 30, "balance": 50.0})

vector = store.get_online_vector("acct:1", ["age", "balance", "double_balance"])
print(vector.values)
print(vector.missing)
```

## 🔧 Error Handling

```text
FeatureStoreError
├── UnknownFeatureError     # get/materialize of undefined feature
└── dtype mismatch errors   # value type ≠ declared dtype
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📝 Code Quality

- Full type hints (`X | None` style), frozen definitions and vectors
- Zero comments — names carry the meaning
- Missing features reported explicitly — never zero-filled

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Kooroush Masoumi**

---

⭐ Star this repo if you find it useful!
