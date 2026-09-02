# Database migrations

The Phase 2 `trades` schema is the first production-oriented schema. New local
databases are created from `database.models.Base.metadata`.

The original prototype schema is not migrated automatically because it lacks
the order identifiers and lifecycle information required to populate the new
non-null columns safely. If an old `trading.db` contains valuable records,
export it before upgrading and write an explicit data mapping. Never run a
destructive automatic migration against production data.
