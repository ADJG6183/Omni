import type { PlasmoCSConfig } from "plasmo"
import { analyzeProduct } from "../utils/apiClient"

// Match all Amazon pages — we decide inside the script whether it's a product page.
// The previous narrow pattern (/dp/*) missed URLs with title slugs like:
// https://www.amazon.com/Sony-WH-1000XM5/dp/B09XS7JWHH
export const config: PlasmoCSConfig = {
  matches: ["https://www.amazon.com/*"],
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
  function parseWholeAndFraction(container: Element): number | null {
    const whole = container.querySelector(".a-price-whole")?.textContent?.replace(/[^0-9]/g, "")
    if (!whole) return null
    const fraction = container.querySelector(".a-price-fraction")?.textContent?.replace(/[^0-9]/g, "") ?? "00"
    const parsed = parseFloat(`${whole}.${fraction}`)
    return isNaN(parsed) || parsed <= 0 ? null : parsed
  }

  // Priority 1: standard desktop buy box
  for (const id of ["corePriceDisplay_desktop_feature_div", "apex_desktop"]) {
    const container = document.getElementById(id)
    if (!container) continue
    const price = parseWholeAndFraction(container)
    if (price) return { value: price }
  }

  // Priority 2: simple inline buy box price
  const inlineEl = document.getElementById("price_inside_buybox")
  if (inlineEl) {
    const parsed = parseFloat(inlineEl.textContent?.replace(/[^0-9.]/g, "") ?? "")
    if (!isNaN(parsed) && parsed > 0) return { value: parsed }
  }

  // Priority 3: fallback — first .a-price on the page
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

let isRunning = false

async function run(url: string) {
  if (isRunning) return
  isRunning = true

  const asin = extractAsin(url)

  // Clear stale result immediately — popup won't show the previous product's data
  chrome.storage.local.set({ omni_result: { loading: true, asin } })

  const titleResult = extractTitle()
  const priceResult = extractPrice()
  const extractionWarnings: string[] = []

  if (titleResult.warning) extractionWarnings.push(titleResult.warning)
  if (priceResult.warning) extractionWarnings.push(priceResult.warning)

  if (!asin) {
    chrome.storage.local.set({
      omni_result: {
        error: true,
        code: "ASIN_NOT_FOUND",
        message: "Could not identify a product ID in this URL. This page may not be a supported product listing.",
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
        message: "Could not read the product title. The page may still be loading — try refreshing.",
        asin,
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
        message: "Could not find a price on this page. The product may be out of stock or require seller selection.",
        asin,
      },
    })
    isRunning = false
    return
  }

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
      omni_result: { loading: false, asin, extractionWarnings, data: result },
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

  isRunning = false
}

// ---------------------------------------------------------------------------
// URL polling — checks every second for navigation to a new product page.
// More reliable than MutationObserver for Amazon's SPA navigation.
// ---------------------------------------------------------------------------

let lastUrl = window.location.href
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Run immediately on first load if this is a product page
if (extractAsin(lastUrl)) {
  run(lastUrl)
} else {
  // Not a product page — clear any leftover result from a previous tab
  chrome.storage.local.set({ omni_result: null })
}

setInterval(() => {
  const currentUrl = window.location.href
  if (currentUrl === lastUrl) return

  lastUrl = currentUrl

  // Debounce: wait 800ms after the URL stops changing before running.
  // Amazon sometimes fires multiple pushState calls in quick succession.
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (extractAsin(currentUrl)) {
      run(currentUrl)
    } else {
      chrome.storage.local.set({ omni_result: null })
    }
  }, 800)
}, 1000)
