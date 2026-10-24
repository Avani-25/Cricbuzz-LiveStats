"""The real app.py must start on a brand-new install with no database."""
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from utils import db_connection as db

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_first_visit_builds_the_database_and_shows_demo_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    db._engine = None
    st.cache_resource.clear()                    # forget any earlier database setup
    assert not (tmp_path / "fresh.db").exists()
    try:
        at = AppTest.from_file(str(APP), default_timeout=90).run()
        assert not at.exception, at.exception
        assert any("Demo mode" in i.value for i in at.sidebar.info)
        assert dict((m.label, m.value) for m in at.metric)["Players"] == "120"
        assert db.table_counts()["matches"] == 450
    finally:
        db.get_engine().dispose()
        db._engine = None
        st.cache_resource.clear()
