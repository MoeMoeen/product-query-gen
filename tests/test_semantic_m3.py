import pytest

pytest.skip(  # type: ignore
    "Semantic resolution/scoring tests disabled due to rollback to M2 (exact-only)",
    allow_module_level=True,
)
