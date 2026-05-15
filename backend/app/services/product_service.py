import re
import logging
from urllib.parse import urlparse, urlunparse, parse_qs

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Product, Retailer
from app.schemas.product import ProductObservation

logger = logging.getLogger(__name__)

_RETAILER_NAME_MAP = {"amazon": "Amazon", "bestbuy": "Best Buy"}

# Fraction of title length that must differ to flag drift
_TITLE_DRIFT_THRESHOLD = 0.40


def extract_retailer_product_id(retailer: str, url: str) -> str | None:
    """Parse the retailer-specific product identifier from a product URL."""
    if retailer == "amazon":
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
        return match.group(1) if match else None

    if retailer == "bestbuy":
        # Primary: numeric segment before .p in the path (/6505727.p)
        path_match = re.search(r"/(\d{6,8})\.p(?:[?#]|$)", url)
        if path_match:
            return path_match[1]
        # Fallback: skuId query param
        query_match = re.search(r"[?&]skuId=(\d+)", url)
        return query_match.group(1) if query_match else None

    return None


def normalize_canonical_url(retailer: str, url: str) -> str:
    """Strip tracking params and produce a stable canonical URL."""
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return url

    if retailer == "amazon":
        match = re.search(r"(/(?:dp|gp/product)/[A-Z0-9]{10})", parsed.path)
        if match:
            return urlunparse((parsed.scheme, parsed.netloc, match.group(1), "", "", ""))

    if retailer == "bestbuy":
        # Anchor on the SKU, not the product slug — the slug changes across
        # page variants and search navigations, making it an unstable key.
        sku = extract_retailer_product_id("bestbuy", url)
        if sku:
            return f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}"
        # Fallback: strip everything except skuId
        qs = parse_qs(parsed.query)
        clean_query = f"skuId={qs['skuId'][0]}" if "skuId" in qs else ""
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", clean_query, ""))

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def get_or_create_product(db: Session, observation: ProductObservation) -> tuple["Product", list[str]]:
    """
    Upsert a product record.

    Lookup order:
    1. retailer_id + retailer_product_id (strongest match)
    2. canonical_url (fallback when product ID is unavailable)

    Returns the product and a list of any data quality warnings.
    Uses a savepoint so a concurrent insert IntegrityError only rolls back
    the insert attempt, not the enclosing transaction.
    """
    warnings: list[str] = []

    retailer_name = _RETAILER_NAME_MAP.get(observation.retailer, observation.retailer)
    retailer = db.query(Retailer).filter(Retailer.name == retailer_name).first()

    if not retailer:
        logger.warning("Retailer not found in DB: %s — creating on the fly", observation.retailer)
        retailer = Retailer(name=retailer_name, domain=f"{observation.retailer}.com")
        db.add(retailer)
        db.flush()

    retailer_product_id = (
        observation.retailer_product_id
        or extract_retailer_product_id(observation.retailer, observation.product_url)
    )

    if not retailer_product_id:
        warnings.append(
            "No product ID found in URL — using URL-based matching, which may be less reliable."
        )

    canonical_url = normalize_canonical_url(observation.retailer, observation.product_url)

    # Try match by retailer + product ID first
    if retailer_product_id:
        product = (
            db.query(Product)
            .filter(
                Product.retailer_id == retailer.id,
                Product.retailer_product_id == retailer_product_id,
            )
            .first()
        )
        if product:
            _check_title_drift(product, observation, warnings)
            _update_product_metadata(product, observation)
            return product, warnings

    # Fallback: match by canonical URL
    product = db.query(Product).filter(Product.canonical_url == canonical_url).first()
    if product:
        _check_title_drift(product, observation, warnings)
        _update_product_metadata(product, observation)
        return product, warnings

    # Create new product — use a savepoint to survive concurrent inserts
    new_product = Product(
        retailer_id=retailer.id,
        retailer_product_id=retailer_product_id,
        canonical_url=canonical_url,
        title=observation.title,
        brand=observation.brand,
        category=observation.category,
        image_url=observation.image_url,
        normalized_title=observation.title.lower().strip(),
    )

    try:
        with db.begin_nested():  # SAVEPOINT — only this block rolls back on conflict
            db.add(new_product)
            db.flush()
        logger.info("Created new product: %s (retailer_product_id=%s)", new_product.id, retailer_product_id)
        return new_product, warnings

    except IntegrityError:
        # Another request raced us and inserted first — re-fetch the winner
        logger.warning(
            "IntegrityError on product insert (concurrent request) — re-fetching existing record"
        )
        if retailer_product_id:
            product = (
                db.query(Product)
                .filter(
                    Product.retailer_id == retailer.id,
                    Product.retailer_product_id == retailer_product_id,
                )
                .first()
            )
        else:
            product = db.query(Product).filter(Product.canonical_url == canonical_url).first()

        if not product:
            raise RuntimeError(
                "Product insert failed with IntegrityError but re-fetch returned nothing"
            )

        _check_title_drift(product, observation, warnings)
        _update_product_metadata(product, observation)
        return product, warnings


def _check_title_drift(product: Product, observation: ProductObservation, warnings: list[str]) -> None:
    """
    Warn when the incoming title differs significantly from what's stored.
    A large drift could mean a product variant mismatch or a page change.
    """
    stored = (product.normalized_title or product.title).lower().strip()
    incoming = observation.title.lower().strip()

    if not stored or not incoming:
        return

    # Compute character-level overlap ratio (simple, no library needed)
    longer = max(len(stored), len(incoming))
    common = sum(a == b for a, b in zip(stored, incoming))
    similarity = common / longer if longer else 1.0

    if similarity < (1.0 - _TITLE_DRIFT_THRESHOLD):
        warnings.append(
            f"Product title has changed significantly from the stored record. "
            f"Stored: '{product.title[:60]}'. Current: '{observation.title[:60]}'. "
            "This may be a different product variant."
        )


def _update_product_metadata(product: Product, observation: ProductObservation) -> None:
    """Fill in missing metadata fields on an existing product."""
    if observation.brand and not product.brand:
        product.brand = observation.brand
    if observation.category and not product.category:
        product.category = observation.category
    if observation.image_url and not product.image_url:
        product.image_url = observation.image_url
