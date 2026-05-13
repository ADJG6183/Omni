"""
Synthetic data seeder for Omni Phase 2.

Inserts 20 realistic electronics products with 90 days of synthetic price
history so the EDA notebooks, feature scripts, and baseline model have
something to work against before real extension data accumulates.

Design decisions
----------------
- Source is tagged "seed" so it can be excluded from production model training
  once real data (source="extension") is plentiful.
- The seeder is fully idempotent: any product whose retailer_product_id already
  exists is skipped.  Safe to run multiple times.
- random.seed(42) makes output reproducible — the same rows every run.
- Price floors prevent any generated price from going negative or unrealistically
  low (minimum 20% of base_price).

Run with:
    cd backend && python -m app.db.seed
"""
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import PriceHistory, Product, Retailer
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_RNG = random.Random(42)  # Isolated RNG — doesn't pollute global state

# ---------------------------------------------------------------------------
# Product catalogue
# ---------------------------------------------------------------------------
# behavior options:
#   volatile  — 3-5 sale events in 90 days (accessories, audio gear)
#   stable    — 0-1 sale events (Apple products, flagship devices)
#   declining — slow price decay + 1-2 dips (older-gen products)

_PRODUCTS = [
    # ------------------------------------------------------------------ Amazon
    {
        "retailer": "Amazon",
        "retailer_product_id": "B09XS7JWHH",
        "title": "Sony WH-1000XM5 Wireless Industry Leading Noise Canceling Headphones",
        "brand": "Sony",
        "category": "electronics",
        "base_price": 349.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B09XS7JWHH",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B0BDHWDR12",
        "title": "Apple AirPods Pro (2nd Generation) Wireless Earbuds with USB-C",
        "brand": "Apple",
        "category": "electronics",
        "base_price": 249.00,
        "behavior": "stable",
        "url": "https://www.amazon.com/dp/B0BDHWDR12",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B09HM94MFL",
        "title": "Logitech MX Master 3S Wireless Performance Mouse",
        "brand": "Logitech",
        "category": "electronics",
        "base_price": 99.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B09HM94MFL",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B09TMP686H",
        "title": "Kindle Paperwhite (16 GB) — 6.8\" display and adjustable warm light",
        "brand": "Amazon",
        "category": "electronics",
        "base_price": 139.99,
        "behavior": "stable",
        "url": "https://www.amazon.com/dp/B09TMP686H",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B098FKXT8L",
        "title": "Bose QuietComfort 45 Bluetooth Wireless Over Ear Headphones",
        "brand": "Bose",
        "category": "electronics",
        "base_price": 279.00,
        "behavior": "declining",
        "url": "https://www.amazon.com/dp/B098FKXT8L",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B08DD9DM7T",
        "title": "Razer BlackWidow V3 Mechanical Gaming Keyboard",
        "brand": "Razer",
        "category": "electronics",
        "base_price": 139.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B08DD9DM7T",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B08XW3TGKV",
        "title": "JBL Charge 5 Portable Bluetooth Speaker with IP67 Waterproof",
        "brand": "JBL",
        "category": "electronics",
        "base_price": 179.95,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B08XW3TGKV",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B08X5ZJTWN",
        "title": "WD_BLACK 2TB SN850X NVMe Internal Gaming SSD",
        "brand": "Western Digital",
        "category": "electronics",
        "base_price": 124.99,
        "behavior": "declining",
        "url": "https://www.amazon.com/dp/B08X5ZJTWN",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B0779KWDP5",
        "title": "TP-Link AX3000 WiFi 6 Router (Archer AX55)",
        "brand": "TP-Link",
        "category": "electronics",
        "base_price": 79.99,
        "behavior": "declining",
        "url": "https://www.amazon.com/dp/B0779KWDP5",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B0BVBF4CHQ",
        "title": "Garmin Forerunner 265 Running Smartwatch with AMOLED Display",
        "brand": "Garmin",
        "category": "electronics",
        "base_price": 449.99,
        "behavior": "stable",
        "url": "https://www.amazon.com/dp/B0BVBF4CHQ",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B0CF5JZ5V3",
        "title": "GoPro HERO12 Black Waterproof Action Camera with 5.3K60 Ultra HD Video",
        "brand": "GoPro",
        "category": "electronics",
        "base_price": 399.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B0CF5JZ5V3",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B09V3HN1KC",
        "title": "Apple iPad Air (5th Generation) with M1 chip, 10.9-inch Liquid Retina Display",
        "brand": "Apple",
        "category": "electronics",
        "base_price": 599.00,
        "behavior": "stable",
        "url": "https://www.amazon.com/dp/B09V3HN1KC",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B08P2BZMZB",
        "title": "Canon EOS M50 Mark II Mirrorless Camera Kit with EF-M 15-45mm Lens",
        "brand": "Canon",
        "category": "electronics",
        "base_price": 649.00,
        "behavior": "declining",
        "url": "https://www.amazon.com/dp/B08P2BZMZB",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B09MNLXMHN",
        "title": "Anker 735 Charger Nano II 65W PPS 3-Port Compact Foldable USB-C Wall Charger",
        "brand": "Anker",
        "category": "electronics",
        "base_price": 35.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B09MNLXMHN",
    },
    {
        "retailer": "Amazon",
        "retailer_product_id": "B0C3QNF4VJ",
        "title": "Samsung Galaxy Buds2 Pro True Wireless Bluetooth Earbuds",
        "brand": "Samsung",
        "category": "electronics",
        "base_price": 199.99,
        "behavior": "volatile",
        "url": "https://www.amazon.com/dp/B0C3QNF4VJ",
    },
    # --------------------------------------------------------------- Best Buy
    {
        "retailer": "Best Buy",
        "retailer_product_id": "6461557",
        "title": "Logitech - G Pro X Superlight 2 DEX Wireless Gaming Mouse",
        "brand": "Logitech",
        "category": "electronics",
        "base_price": 159.99,
        "behavior": "declining",
        "url": "https://www.bestbuy.com/site/logitech/6461557.p?skuId=6461557",
    },
    {
        "retailer": "Best Buy",
        "retailer_product_id": "6571516",
        "title": "Samsung - Galaxy Tab S9 FE 10.9\" 128GB Wi-Fi Android Tablet",
        "brand": "Samsung",
        "category": "electronics",
        "base_price": 449.99,
        "behavior": "stable",
        "url": "https://www.bestbuy.com/site/samsung/6571516.p?skuId=6571516",
    },
    {
        "retailer": "Best Buy",
        "retailer_product_id": "6536841",
        "title": "Dell - XPS 15 15.6\" OLED Touch Laptop Intel Core i7 16GB Memory 512GB SSD",
        "brand": "Dell",
        "category": "electronics",
        "base_price": 1599.99,
        "behavior": "stable",
        "url": "https://www.bestbuy.com/site/dell/6536841.p?skuId=6536841",
    },
    {
        "retailer": "Best Buy",
        "retailer_product_id": "6501493",
        "title": "LG - 27GP850-B 27\" Ultragear QHD IPS Gaming Monitor 165Hz",
        "brand": "LG",
        "category": "electronics",
        "base_price": 299.99,
        "behavior": "volatile",
        "url": "https://www.bestbuy.com/site/lg/6501493.p?skuId=6501493",
    },
    {
        "retailer": "Best Buy",
        "retailer_product_id": "6505727",
        "title": "Sony - WH-1000XM5 Wireless Noise-Canceling Over-Ear Headphones",
        "brand": "Sony",
        "category": "electronics",
        "base_price": 329.99,
        "behavior": "volatile",
        "url": "https://www.bestbuy.com/site/sony/6505727.p?skuId=6505727",
    },
]

# ---------------------------------------------------------------------------
# Price generation
# ---------------------------------------------------------------------------

_PRICE_FLOOR_RATIO = 0.20   # Price can never go below 20% of base


def _generate_price_series(
    base_price: float,
    behavior: str,
    days: int = 90,
) -> list[tuple[datetime, float]]:
    """
    Generate a realistic list of (timestamp, price) observations.

    Only rows where the price actually changed are included — matching the
    dedup behavior of the real price_service.  The result is sorted by time.

    Edge cases handled
    ------------------
    - Price floor: no price ever drops below _PRICE_FLOOR_RATIO × base_price.
    - Always at least 2 rows (open + at least one change) so every product
      has enough history for feature computation.
    - Timestamps are UTC-aware and spread across the 90-day window with a
      random hour-of-day offset so they look like real browser observations.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    price_floor = round(base_price * _PRICE_FLOOR_RATIO, 2)

    # Each entry is (day_offset: int, price: float)
    events: list[tuple[int, float]] = [(0, base_price)]

    if behavior == "volatile":
        num_sales = _RNG.randint(3, 5)
        # Space sale starts so they don't overlap
        sale_days = sorted(_RNG.sample(range(5, days - 15), num_sales))
        current_base = base_price

        for sale_day in sale_days:
            drop_pct = _RNG.uniform(0.10, 0.22)
            sale_price = max(round(current_base * (1 - drop_pct), 2), price_floor)
            sale_duration = _RNG.randint(5, 10)
            events.append((sale_day, sale_price))

            # Recovery — partial (prices rarely fully recover)
            recovery_day = min(sale_day + sale_duration, days - 1)
            recovery_price = round(current_base * _RNG.uniform(0.96, 1.02), 2)
            events.append((recovery_day, recovery_price))

            # Slight permanent base drift after each sale cycle
            current_base = round(current_base * _RNG.uniform(0.97, 1.01), 2)

    elif behavior == "stable":
        num_sales = _RNG.randint(0, 1)
        if num_sales == 1:
            sale_day = _RNG.randint(20, 65)
            drop_pct = _RNG.uniform(0.05, 0.12)
            sale_price = max(round(base_price * (1 - drop_pct), 2), price_floor)
            sale_duration = _RNG.randint(7, 14)
            events.append((sale_day, sale_price))
            recovery_day = min(sale_day + sale_duration, days - 1)
            events.append((recovery_day, round(base_price * _RNG.uniform(0.97, 1.02), 2)))

    elif behavior == "declining":
        # Gradual overall decline of 10-18% across the period
        total_decline = _RNG.uniform(0.10, 0.18)
        num_dips = _RNG.randint(1, 2)

        for i in range(num_dips):
            # Spread dips across the 90-day window
            dip_day = _RNG.randint(10 + i * 30, 35 + i * 30)
            price_at_dip = base_price * (1 - total_decline * dip_day / days)
            events.append((dip_day, round(price_at_dip, 2)))

            # Short sharp dip then partial recovery
            drop_price = max(round(price_at_dip * _RNG.uniform(0.85, 0.92), 2), price_floor)
            events.append((dip_day + 2, drop_price))
            recovery_day = min(dip_day + _RNG.randint(5, 10), days - 1)
            events.append((recovery_day, round(price_at_dip * _RNG.uniform(0.93, 0.99), 2)))

        # Final settled price at end of period
        final_price = max(round(base_price * (1 - total_decline), 2), price_floor)
        events.append((days - 1, final_price))

    # Sort by day, dedup consecutive same prices, convert to timestamps
    events.sort(key=lambda e: e[0])
    result: list[tuple[datetime, float]] = []
    last_price: float | None = None

    for day_offset, price in events:
        price = max(price, price_floor)  # Hard floor guard
        if price == last_price:
            continue
        ts = start + timedelta(days=day_offset, hours=_RNG.randint(8, 21))
        result.append((ts, round(price, 2)))
        last_price = price

    # Guarantee at least 2 rows — if only 1 was generated, add a tiny change
    if len(result) == 1:
        ts = result[0][0] + timedelta(days=7)
        result.append((ts, round(result[0][1] * 0.95, 2)))

    return result


# ---------------------------------------------------------------------------
# Core seeder
# ---------------------------------------------------------------------------

def seed(db: Session) -> dict[str, int]:
    """
    Insert synthetic products and price history.

    Returns a dict with "products" and "prices" counts inserted this run.
    Any product whose retailer_product_id is already present is skipped so
    the function is safe to call repeatedly.
    """
    products_inserted = 0
    prices_inserted = 0

    for spec in _PRODUCTS:
        retailer = db.query(Retailer).filter(Retailer.name == spec["retailer"]).first()
        if not retailer:
            logger.error(
                "Retailer '%s' not found — run `alembic upgrade head` first.",
                spec["retailer"],
            )
            continue

        # Idempotency: skip if this product is already in the DB
        existing = (
            db.query(Product)
            .filter(
                Product.retailer_id == retailer.id,
                Product.retailer_product_id == spec["retailer_product_id"],
            )
            .first()
        )
        if existing:
            logger.debug(
                "Skipping '%s' (%s) — already seeded.",
                spec["retailer_product_id"],
                spec["retailer"],
            )
            continue

        product = Product(
            retailer_id=retailer.id,
            retailer_product_id=spec["retailer_product_id"],
            canonical_url=spec["url"],
            title=spec["title"],
            brand=spec["brand"],
            category=spec["category"],
            normalized_title=spec["title"].lower().strip(),
        )
        db.add(product)
        db.flush()  # Populate product.id before referencing it

        price_series = _generate_price_series(spec["base_price"], spec["behavior"])

        for ts, price in price_series:
            db.add(
                PriceHistory(
                    product_id=product.id,
                    price=Decimal(str(price)),
                    currency="USD",
                    availability="in_stock",
                    observed_at=ts,
                    source="seed",
                )
            )
        prices_inserted += len(price_series)
        products_inserted += 1

        logger.info(
            "Seeded %-45s  %d observations  (behavior=%s)",
            spec["title"][:45],
            len(price_series),
            spec["behavior"],
        )

    db.commit()
    return {"products": products_inserted, "prices": prices_inserted}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    db = SessionLocal()
    try:
        counts = seed(db)
        if counts["products"] == 0:
            print("Nothing to seed — all products already exist.")
        else:
            print(
                f"\nSeeded {counts['products']} products "
                f"with {counts['prices']} price observations."
            )
    except Exception:
        logger.exception("Seeder failed")
        sys.exit(1)
    finally:
        db.close()
