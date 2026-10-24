"""A safety net around every page (messages live in utils/friendly.py)."""
import logging
import uuid

import streamlit as st

import config
from utils.friendly import friendly_error

logger = logging.getLogger(__name__)


def handle_page_errors(run_page) -> None:
    """Run a page; on failure log the full traceback and show a short message.

    st.stop() and st.rerun() raise BaseException subclasses, so they pass through.
    """
    try:
        run_page()
    except Exception as exc:
        error_id = uuid.uuid4().hex[:8]
        logger.exception("Unhandled error in page [%s]", error_id)
        st.error(f"{friendly_error(exc)}  \n\nReference: `{error_id}` (see logs/cricbuzz.log)")
        if getattr(config, "DEBUG", False):
            st.exception(exc)
