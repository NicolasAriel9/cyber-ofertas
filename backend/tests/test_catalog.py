"""The API's in-memory catalog reads the listing table once, then only the
rows written since."""

from sqlalchemy import event

from app.catalog import Catalog
from app.models import Category, Store
from tests.test_highlights import _listing


def test_refresh_reads_only_what_changed(db_session):
    tech = Category(name="Tecnología", slug="tecnologia")
    paris = Store(name="Paris", slug="paris")
    db_session.add_all([tech, paris])
    db_session.flush()
    tv = _listing(db_session, paris, tech, "TV", 300_000, 600_000)
    ended = _listing(db_session, paris, tech, "Se acabó", 10_000, 20_000)
    for i in range(5):
        _listing(db_session, paris, tech, f"Sin cambios {i}", 10_000, 20_000)
    db_session.flush()

    catalog = Catalog()
    catalog.enabled = True
    assert len(catalog.get(db_session).live()) == 7

    tv.current_price = 250_000
    ended.is_active = False
    _listing(db_session, paris, tech, "Nueva", 5_000, 10_000)
    db_session.flush()

    rows_read = []
    listener = lambda conn, cursor, statement, params, context, executemany: rows_read.append(  # noqa: E731
        statement)
    event.listen(db_session.get_bind(), "before_cursor_execute", listener)
    try:
        catalog._load(db_session)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", listener)

    live = {r.title: r for r in catalog.get(db_session).live("productos")}
    assert "se acabó" not in live
    assert live["tv"].price == 250_000
    assert "nueva" in live
    assert len(live) == 7
    assert any("updated_at >=" in s for s in rows_read)  # not a full read
