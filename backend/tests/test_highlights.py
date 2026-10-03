from datetime import timedelta

from app.models import Category, Favorite, Listing, PriceSnapshot, Product, Store, Subscriber, utcnow
from app.routers import listings as listings_router
from app.routers.favorites import list_favorites


def _listing(db, store, category, title, price, original, product=None):
    if product is None:
        product = Product(canonical_title=title, category_id=category.id)
        db.add(product)
        db.flush()
    listing = Listing(
        product_id=product.id,
        store_id=store.id,
        external_id=f"{store.slug}-{title}",
        title=title,
        url=f"https://{store.slug}.cl/{title}",
        current_price=price,
        current_original_price=original,
        current_discount_pct=round((original - price) / original * 100, 2),
    )
    db.add(listing)
    db.flush()
    return listing


def test_highlights_rank_by_savings_and_skip_bogus_discounts(db_session):
    listings_router._highlights_cache.clear()
    tech = Category(name="Tecnología", slug="tecnologia")
    paris, ripley, hites = (Store(name=n, slug=n.lower()) for n in ("Paris", "Ripley", "Hites"))
    db_session.add_all([tech, paris, ripley, hites])
    db_session.flush()

    tv = _listing(db_session, paris, tech, "Smart TV 55", 300_000, 750_000)  # -60%, saves 450k
    _listing(db_session, paris, tech, "Cable HDMI", 2_000, 9_000)  # -78% but saves only 7k
    _listing(db_session, ripley, tech, "Mouse", 1_000, 50_000)  # -98%: bogus
    notebook = _listing(db_session, ripley, tech, "Notebook", 400_000, 800_000)  # -50%
    # Same TV in another store: must not show up twice.
    _listing(db_session, hites, tech, "Smart TV 55 Hites", 310_000, 750_000, product=tv.product)

    [highlight] = listings_router.list_highlights(per_category=3, section="productos", db=db_session)

    assert highlight.category.slug == "tecnologia"
    assert highlight.total == 5
    titles = [l.title for l in highlight.listings]
    assert titles[:2] == [tv.title, notebook.title]
    assert "Mouse" not in titles
    assert titles.count("Smart TV 55") + titles.count("Smart TV 55 Hites") == 1


def test_favorite_reports_price_change_since_added(db_session):
    tech = Category(name="Tecnología", slug="tecnologia")
    paris = Store(name="Paris", slug="paris")
    nico = Subscriber(name="Nico")
    db_session.add_all([tech, paris, nico])
    db_session.flush()

    listing = _listing(db_session, paris, tech, "Smart TV 55", 300_000, 750_000)
    now = utcnow()
    db_session.add_all(
        [
            PriceSnapshot(listing_id=listing.id, price=350_000, scraped_at=now - timedelta(days=2)),
            PriceSnapshot(listing_id=listing.id, price=300_000, scraped_at=now - timedelta(hours=1)),
            Favorite(subscriber_id=nico.id, product_id=listing.product_id, created_at=now - timedelta(days=1)),
        ]
    )
    db_session.flush()

    [favorite] = list_favorites(subscriber_id=nico.id, db=db_session)

    assert favorite.price_when_added == 350_000
    assert favorite.product.best_price == 300_000
    assert favorite.product.lowest_price == 300_000
    assert favorite.product.best_url == "https://paris.cl/Smart TV 55"
    assert favorite.product.store_count == 1
