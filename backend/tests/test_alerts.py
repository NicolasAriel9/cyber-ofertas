from app.models import Favorite, Listing, PriceSnapshot, Product, Store, Subscriber
from app.services.alerts import check_price_drop, record_alert_sent


def _seed_listing_with_price(db_session, price: float) -> tuple[Listing, PriceSnapshot]:
    store = Store(name="Falabella", slug="falabella")
    product = Product(canonical_title="Notebook Lenovo IdeaPad 3")
    db_session.add_all([store, product])
    db_session.flush()

    listing = Listing(
        product_id=product.id,
        store_id=store.id,
        external_id="falabella-123",
        title="Notebook Lenovo IdeaPad 3",
        url="https://falabella.com/p/123",
    )
    db_session.add(listing)
    db_session.flush()

    snapshot = PriceSnapshot(listing_id=listing.id, price=price)
    db_session.add(snapshot)
    db_session.flush()
    return listing, snapshot


def test_no_alert_on_first_snapshot(db_session):
    listing, snapshot = _seed_listing_with_price(db_session, 349990)
    assert check_price_drop(db_session, listing, snapshot) == []


def test_alert_when_target_price_met(db_session):
    listing, first_snapshot = _seed_listing_with_price(db_session, 349990)
    subscriber = Subscriber(name="Nico", telegram_chat_id=111)
    db_session.add(subscriber)
    db_session.flush()
    favorite = Favorite(subscriber_id=subscriber.id, product_id=listing.product_id, target_price=300000)
    db_session.add(favorite)
    db_session.flush()

    new_snapshot = PriceSnapshot(listing_id=listing.id, price=299990)
    db_session.add(new_snapshot)
    db_session.flush()
    db_session.refresh(listing)

    alerts = check_price_drop(db_session, listing, new_snapshot)
    assert len(alerts) == 1
    assert alerts[0].new_price == 299990


def test_no_alert_when_target_not_met(db_session):
    listing, first_snapshot = _seed_listing_with_price(db_session, 349990)
    subscriber = Subscriber(name="Nico", telegram_chat_id=111)
    db_session.add(subscriber)
    db_session.flush()
    favorite = Favorite(subscriber_id=subscriber.id, product_id=listing.product_id, target_price=250000)
    db_session.add(favorite)
    db_session.flush()

    new_snapshot = PriceSnapshot(listing_id=listing.id, price=320000)
    db_session.add(new_snapshot)
    db_session.flush()
    db_session.refresh(listing)

    assert check_price_drop(db_session, listing, new_snapshot) == []


def test_alert_deduplicated_on_second_check(db_session):
    listing, first_snapshot = _seed_listing_with_price(db_session, 349990)
    subscriber = Subscriber(name="Nico", telegram_chat_id=111)
    db_session.add(subscriber)
    db_session.flush()
    favorite = Favorite(subscriber_id=subscriber.id, product_id=listing.product_id, target_price=300000)
    db_session.add(favorite)
    db_session.flush()

    new_snapshot = PriceSnapshot(listing_id=listing.id, price=299990)
    db_session.add(new_snapshot)
    db_session.flush()
    db_session.refresh(listing)

    alerts = check_price_drop(db_session, listing, new_snapshot)
    assert len(alerts) == 1
    record_alert_sent(db_session, alerts[0])
    db_session.commit()

    # Simulate a later scrape cycle re-checking the same snapshot state.
    assert check_price_drop(db_session, listing, new_snapshot) == []
