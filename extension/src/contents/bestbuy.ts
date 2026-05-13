import type { PlasmoCSConfig } from "plasmo"
import { analyzeProduct } from "../utils/apiClient"

// Match all Best Buy pages — SKU check inside decides if it's a product page.
export const config: PlasmoCSConfig = {
  matches: ["https://www.bestbuy.com/*"],
  run_at: "document_idle",
}

// ---------------------------------------------------------------------------
// Extraction helpers
// ---------------------------------------------------------------------------

function extractSku(url: string): string | null {
  // Primary: SKU is the numeric segment before .p in the URL path.
  // e.g. /site/sony-.../6505727.p  or  /6505727.p?skuId=6505727
  const pathMatch = url.match(/\/(\d{6,8})\.p(?:[?#]|$)/)
  if (pathMatch) return pathMatch[1]
  // Fallback: skuId query param (some navigation paths use this)
  const queryMatch = url.match(/[?&]skuId=(\d+)/)
  return queryMatch ? queryMatch[1] : null
}

function extractTitle(): { value: string | null; warning?: string } {
  // Best Buy uses a single h1 on product pages.
  // Try the most specific class first, then fall back to any h1.
  const selectors = ["h1.heading-5", "h1[class*='heading']", "h1"]
  for (const sel of selectors) {
    const el = document.querySelector(sel)
    const text = el?.textContent?.trim() ?? null
    if (!text) continue
    if (text.length < 5) {
      return {
        value: text,
        warning: "Product title is unusually short — may not reflect the full product name.",
      }
    }
    return { value: text }
  }
  return { value: null }
}

interface PriceResult {
  value: number | null
  warning?: string
}

function extractPrice(): PriceResult {
  // Detect "See price in cart" — Best Buy hides prices for certain products
  // until the user adds them to cart. There is no extractable price.
  const seeInCart = document.querySelector(
    ".priceView-see-price-in-cart, [data-testid='see-in-cart']"
  )
  if (seeInCart) {
    return {
      value: null,
      warning:
        "Best Buy is showing 'See price in cart' — the price cannot be read from this page.",
    }
  }

  // Priority 1: customer price block — the main new-item price
  const customerPriceEl = document.querySelector(
    ".priceView-customer-price, [data-testid='customer-price']"
  )
  if (customerPriceEl) {
    // Best Buy renders an aria-hidden span with the visible price text
    // and a .sr-only span with the screen-reader version.
    // We want the aria-hidden one first.
    const ariaHidden = customerPriceEl.querySelector("span[aria-hidden='true']")
    if (ariaHidden) {
      const parsed = parseFloat(ariaHidden.textContent?.replace(/[^0-9.]/g, "") ?? "")
      if (!isNaN(parsed) && parsed > 0) return { value: parsed }
    }
    // Fallback: parse any text inside the price container
    const text = customerPriceEl.textContent?.replace(/[^0-9.]/g, "") ?? ""
    const parsed = parseFloat(text)
    if (!isNaN(parsed) && parsed > 0) return { value: parsed }
  }

  // Priority 2: generic .priceView-price fallback (older/alternative page layouts)
  const fallbackEl = document.querySelector(".priceView-price")
  if (fallbackEl) {
    const text = fallbackEl.textContent?.replace(/[^0-9.]/g, "") ?? ""
    const parsed = parseFloat(text)
    if (!isNaN(parsed) && parsed > 0) {
      return {
        value: parsed,
        warning:
          "Price extracted from fallback selector — could not find the primary price block. Verify this price is correct.",
      }
    }
  }

  return { value: null }
}

function extractBrand(): string | null {
  const el = document.querySelector(
    ".shop-brand-name, [data-testid='brand-name'], .brand-link"
  )
  return el?.textContent?.trim() ?? null
}

function extractAvailability(): string {
  // "Add to Cart" button present and enabled → in stock.
  // Button disabled with "Sold Out" state → out of stock.
  const soldOutBtn = document.querySelector(
    ".btn[data-button-state='SOLD_OUT'], .btn-disabled[aria-label*='Sold']"
  )
  if (soldOutBtn) return "out_of_stock"

  const addToCartBtn = document.querySelector(
    "[data-button-state='ADD_TO_CART'], .add-to-cart-button:not(.btn-disabled)"
  )
  if (addToCartBtn) return "in_stock"

  return "unknown"
}

function extractImageUrl(): string | null {
  return (
    (
      document.querySelector(
        ".primary-image img, [data-testid='primary-product-image']"
      ) as HTMLImageElement | null
    )?.src ?? null
  )
}

// ---------------------------------------------------------------------------
// Main runner
// ---------------------------------------------------------------------------

let isRunning = false

async function run(url: string) {
  if (isRunning) return
  isRunning = true

  const sku = extractSku(url)

  chrome.storage.local.set({ omni_result: { loading: true, asin: sku } })

  const titleResult = extractTitle()
  const priceResult = extractPrice()
  const extractionWarnings: string[] = []

  if (titleResult.warning) extractionWarnings.push(titleResult.warning)
  if (priceResult.warning) extractionWarnings.push(priceResult.warning)

  if (!sku) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "SKU_NOT_FOUND",
        message:
          "Could not identify a product ID in this URL. This page may not be a supported product listing.",
        asin: null,
      },
    })
    isRunning = false
    return
  }

  if (!titleResult.value) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "TITLE_NOT_FOUND",
        message:
          "Could not read the product title. The page may still be loading — try refreshing.",
        asin: sku,
      },
    })
    isRunning = false
    return
  }

  if (priceResult.value === null) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "PRICE_NOT_FOUND",
        message:
          priceResult.warning ??
          "Could not find a price on this page. The product may be out of stock or require cart selection.",
        asin: sku,
      },
    })
    isRunning = false
    return
  }

  try {
    const result = await analyzeProduct({
      retailer: "bestbuy",
      product_url: url,
      title: titleResult.value,
      price: priceResult.value,
      currency: "USD",
      availability: extractAvailability(),
      image_url: extractImageUrl() ?? undefined,
      brand: extractBrand() ?? undefined,
      retailer_product_id: sku,
    })

    chrome.storage.local.set({
      omni_result: { loading: false, asin: sku, extractionWarnings, data: result },
    })
  } catch (err: any) {
    chrome.storage.local.set({
      omni_result: {
        loading: false,
        error: true,
        code: "API_ERROR",
        message:
          err.message ?? "Could not reach the Omni backend. Make sure the server is running.",
        asin: sku,
      },
    })
  }

  isRunning = false
}

// ---------------------------------------------------------------------------
// URL polling — same pattern as amazon.ts
// ---------------------------------------------------------------------------

let lastUrl = window.location.href
let debounceTimer: ReturnType<typeof setTimeout> | null = null

if (extractSku(lastUrl)) {
  run(lastUrl)
} else {
  chrome.storage.local.set({ omni_result: null })
}

setInterval(() => {
  const currentUrl = window.location.href
  if (currentUrl === lastUrl) return

  lastUrl = currentUrl

  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (extractSku(currentUrl)) {
      run(currentUrl)
    } else {
      chrome.storage.local.set({ omni_result: null })
    }
  }, 800)
}, 1000)
