import pytest
from app.services.product_service import extract_retailer_product_id, normalize_canonical_url


class TestExtractRetailerProductId:
    def test_amazon_standard_dp_url(self):
        url = "https://www.amazon.com/dp/B09XS7JWHH"
        assert extract_retailer_product_id("amazon", url) == "B09XS7JWHH"

    def test_amazon_gp_product_url(self):
        url = "https://www.amazon.com/gp/product/B09XS7JWHH/ref=sr_1_1"
        assert extract_retailer_product_id("amazon", url) == "B09XS7JWHH"

    def test_amazon_url_with_title_slug(self):
        url = "https://www.amazon.com/Sony-WH-1000XM5-Wireless/dp/B09XS7JWHH?th=1"
        assert extract_retailer_product_id("amazon", url) == "B09XS7JWHH"

    def test_amazon_no_asin(self):
        url = "https://www.amazon.com/s?k=headphones"
        assert extract_retailer_product_id("amazon", url) is None

    def test_bestbuy_sku_url(self):
        url = "https://www.bestbuy.com/site/product.p?skuId=6505727"
        assert extract_retailer_product_id("bestbuy", url) == "6505727"

    def test_bestbuy_no_sku(self):
        url = "https://www.bestbuy.com/site/searchpage.jsp?st=headphones"
        assert extract_retailer_product_id("bestbuy", url) is None

    def test_unknown_retailer_returns_none(self):
        assert extract_retailer_product_id("walmart", "https://walmart.com/ip/123") is None


class TestNormalizeCanonicalUrl:
    def test_amazon_strips_to_dp_path(self):
        url = "https://www.amazon.com/Sony-WH-1000XM5/dp/B09XS7JWHH?ref=sr_1_1&th=1"
        result = normalize_canonical_url("amazon", url)
        assert result == "https://www.amazon.com/dp/B09XS7JWHH"

    def test_amazon_no_asin_falls_back(self):
        url = "https://www.amazon.com/s?k=headphones"
        result = normalize_canonical_url("amazon", url)
        # Fallback strips query params entirely
        assert "k=headphones" not in result

    def test_bestbuy_keeps_only_skuid(self):
        url = "https://www.bestbuy.com/site/product.p?skuId=6505727&intl=nosplash"
        result = normalize_canonical_url("bestbuy", url)
        assert "skuId=6505727" in result
        assert "intl" not in result
