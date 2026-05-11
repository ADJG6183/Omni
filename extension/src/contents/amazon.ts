import type { PlasmoCSConfig } from "plasmo"
import { analyzeProduct } from "../utils/apiClient"

export const config: PlasmoCSConfig = {
  matches: ["https://www.amazon.com/dp/*", "https://www.amazon.com/gp/product/*"],
  run_at: "document_idle",
}

// ---------------------------------------------------------------------------
// Extraction helpers
// ---------------------------------------------------------------------------

function extractAsin(url: string): string | null {
  const match = url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/)
  return match ? match[1] : null
}

function extractTitle(): { value: string | null; warning?: string } {
  const el = document.getElementById("productTitle")
  const text = el?.textContent?.trim() ?? null
  if (!text) return { value: null }
  if (text.length < 10) {
    return { value: text, warning: "Product title is unusually short — may not reflect the full product name." }
  }
  return { value: text }
}

interface PriceResult {
  value: number | null
  warning?: string
}

function extractPrice(): PriceResult {
  // Helper: parse a whole + fraction pair from a parent element
  function parseWholeAndFraction(container: Element): number | null {
    const whole = container.querySelector(".a-price-whole")?.textContent?.replace(/[^0-9]/g, "")
    if (!whole) return null
    const fraction = container.querySelector(".a-price-fraction")?.textContent?.replace(/[^0-9]/g, "") ?? "00"
    const parsed = parseFloat(`${whole}.${fraction}`)
    return isNaN(parsed) || parsed <= 0 ? null : parsed
  }

  // Priority 1: standard desktop buy box — the most reliable source
  const buyBoxContainers = [
    document.getElementById("corePriceDisplay_desktop_feature_div"),
    document.getElementById("apex_desktop"),
  ]
  for (const container of buyBoxContainers) {
    if (!container) continue
    const price = parseWholeAndFraction(container)
    if (price) return { value: price }
  }

  // Priority 2: simple inline buy box price (e.g. "$249.99" in a single span)
  const inlineEl = document.getElementById("price_inside_buybox")
  if (inlineEl) {
    const text = inlineEl.textContent?.replace(/[^0-9.]/g, "") ?? ""
    const parsed = parseFloat(text)
    if (!isNaN(parsed) && parsed > 0) return { value: parsed }
  }

  // Priority 3: fallback — first .a-price on the page (may not be the buy price)
  const fallbackContainer = document.querySelector(".a-price")
  if (fallbackContainer) {
    const price = parseWholeAndFraction(fallbackContainer)
    if (price) {
      return {
        value: price,
        warning: "Price extracted from fallback selector — could not find the primary buy box. Verify this price is correct.",
      }
    }
  }

  return { value: null }
}

function extractBrand(): string | null {
  return (
    document.querySelector("#bylineInfo")?.textContent
      ?.replace(/^(Visit the|Brand:|by)\s*/i, "")
      .trim() ?? null
  )
}

function extractAvailability(): string {
  const text = document.getElementById("availability")?.textContent?.trim().toLowerCase() ?? ""
  if (text.includes("in stock")) return "in_stock"
  if (text.includes("out of stock")) return "out_of_stock"
  return "unknown"
}

function extractImageUrl(): string | null {
  return (document.getElementById("landingImage") as HTMLImageElement | null)?.src ?? null
}

// ---------------------------------------------------------------------------
// Main runner
// ---------------------------------------------------------------------------

async function run(url: string) {
  const asin = extractAsin(url)

  // Clear any previous result immediately — prevents the popup from showing
  // a stale result from the last page while this analysis is in progress.
  chrome.storage.local.set({ omni_result: { loading: true, asin } })

  // --- Field extraction with per-field diagnostics ---
  const titleResult = extractTitle()
  const priceResult = extractPrice()
  const extractionWarnings: string[] = []

  if (titleResult.warning) extractionWarnings.push(titleResult.warning)
  if (priceResult.warning) extractionWarnings.push(priceResult.warning)

  // Hard stop: can't build a meaningful result without these three
  if (!asin) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "ASIN_NOT_FOUND",
        message: "Could not identify a product ID in this URL. This page may not be a supported product listing.",
        asin: null,
      },
    })
    return
  }

  if (!titleResult.value) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "TITLE_NOT_FOUND",
        message: "Could not read the product title. The page may still be loading — try refreshing.",
        asin,
      },
    })
    return
  }

  if (priceResult.value === null) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "PRICE_NOT_FOUND",
        message: "Could not find a price on this page. The product may be out of stock or require seller selection.",
        asin,
      },
    })
    return
  }

  // --- API call ---
  try {
    const result = await analyzeProduct({
      retailer: "amazon",
      product_url: url,
      title: titleResult.value,
      price: priceResult.value,
      currency: "USD",
      availability: extractAvailability(),
      image_url: extractImageUrl() ?? undefined,
      brand: extractBrand() ?? undefined,
      retailer_product_id: asin,
    })

    chrome.storage.local.set({
      omni_result: {
        loading: false,
        asin,
        extractionWarnings,
        data: result,
      },
    })
  } catch (err: any) {
    chrome.storage.local.set({
      omni_result: {
        loading: false,
        error: true,
        code: "API_ERROR",
        message: err.message ?? "Could not reach the Omni backend. Make sure the server is running.",
        asin,
      },
    })
  }
}

// ---------------------------------------------------------------------------
// Entry point — also re-run on SPA navigation (Amazon uses pushState)
// ---------------------------------------------------------------------------

let lastUrl = window.location.href
run(lastUrl)

// Detect client-side URL changes (Amazon SPA navigation between products)
const observer = new MutationObserver(() => {
  const currentUrl = window.location.href
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl
    if (extractAsin(currentUrl)) {
      run(currentUrl)
    }
  }
})

observer.observe(document.body, { childList: true, subtree: true })
