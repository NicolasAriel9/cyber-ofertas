import pytest

from app.scraper.parser import parse_category_html


def test_parser_not_yet_implemented():
    """cyber.cl's real catalog markup wasn't available during Phase 0
    inspection (see docs/cyber_cl_inspection_notes.md) -- this test documents
    that parse_category_html is a placeholder pending a re-inspection closer
    to the event, rather than silently passing."""
    with pytest.raises(NotImplementedError):
        parse_category_html("<html></html>", "tecnologia")
