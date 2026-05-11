import re
import logging
from urllib.parse import urlparse, urlunparse, parse_qs

from sqlalchemy.orm import Session

from app.db.models import Product, Retailer
from app.schemas.product import ProductObservation

logger = logging.getLogger(__name__)


def extract_retailer_product_id(retailer: str, url: str) -> str | None:
    """Parse the retailer-specific product identifier from a product URL."""
    if retailer == "amazon":
        # Amazon product URLs contain /dp/ASIN or /gp/product/ASIN
        match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
        return match.group(1) if match else None

    if retailer == "bestbuy":
        # Best Buy URLs end with .p?skuId=XXXXXXX
        match = re.search(r"skuId=(\d+)", url)
        return match.group(1) if match else None

    return None


def normalize_canonical_url(retailer: str, url: str) -> str:
    """Strip tracking params and produce a stable canonical URL."""
    parsed = urlparse(url)

    if retailer == "amazon":
        # Keep only the /dp/ASIN path, drop all query params
        match = re.search(r"(/(?:dp|gp/product)/[A-Z0-9]{10})", parsed.path)
        if match:
            return urlunparse((parsed.scheme, parsed.netloc, match.group(1), "", "", ""))

    if retailer == "bestbuy":
        # Keep skuId param only
        qs = parse_qs(parsed.query)
        clean_query = f"skuId={qs['skuId'][0]}" if "skuId" in qs else ""
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", clean_query, ""))

    # Fallback: strip all query params
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def get_retailer_by_name(db: Session, retailer_name: str) -> Retailer | None:
    return db.query(Retailer).filter(Retailer.name.ilike(f"%{retailer_name}%")).first()


def get_or_create_product(db: Session, observation: ProductObservation) -> Product:
    """
    Upsert a product record.

    Lookup order:
    1. retailer_id + retailer_product_id (strongest match)
    2. canonical_url (fallback when product ID is unavailable)
    """
    retailer_map = {"amazon": "Amazon", "bestbuy": "Best Buy"}
    retailer_name = retailer_map.get(observation.retailer, observation.retailer)
    retailer = db.query(Retailer).filter(Retailer.name == retailer_name).first()

    if not retailer:
        logger.warning("Retailer not found in DB: %s", observation.retailer)
        # Create it on the fly so we don't fail hard
        retailer = Retailer(name=retailer_name, domain=f"{observation.retailer}.com")
        db.add(retailer)
        db.flush()

    retailer_product_id = (
        observation.retailer_product_id
        or extract_retailer_product_id(observation.retailer, observation.product_url)
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
            _update_product_metadata(product, observation)
            return product

    # Fallback: match by canonical URL
    product = db.query(Product).filter(Product.canonical_url == canonical_url).first()
    if product:
        _update_product_metadata(product, observation)
        return product

    # Create new product
    product = Product(
        retailer_id=retailer.id,
        retailer_product_id=retailer_product_id,
        canonical_url=canonical_url,
        title=observation.title,
        brand=observation.brand,
        category=observation.category,
        image_url=observation.image_url,
        normalized_title=observation.title.lower().strip(),
    )
    db.add(product)
    db.flush()
    logger.info("Created new product: %s (retailer_product_id=%s)", product.id, retailer_product_id)
    return product


def _update_product_metadata(product: Product, observation: ProductObservation) -> None:
    """Refresh mutable fields on an existing product record."""
    if observation.brand and not product.brand:
        product.brand = observation.brand
    if observation.category and not product.category:
        product.category = observation.category
    if observation.image_url and not product.image_url:
        product.image_url = observation.image_url
