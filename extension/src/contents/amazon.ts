import type { PlasmoCSConfig } from "plasmo"
import { analyzeProduct } from "../utils/apiClient"

export const config: PlasmoCSConfig = {
  matches: ["https://www.amazon.com/dp/*", "https://www.amazon.com/gp/product/*"],
  run_at: "document_idle",
}

function extractAsin(url: string): string | null {
  const match = url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/)
  return match ? match[1] : null
}

function extractTitle(): string | null {
  const el = document.getElementById("productTitle")
  return el?.textContent?.trim() ?? null
}

function extractPrice(): number | null {
  // Amazon renders price across two spans: whole + fraction
  const whole = document.querySelector(".a-price-whole")?.textContent?.replace(/[^0-9]/g, "")
  const fraction = document.querySelector(".a-price-fraction")?.textContent?.replace(/[^0-9]/g, "") ?? "00"

  if (!whole) return null
  const parsed = parseFloat(`${whole}.${fraction}`)
  return isNaN(parsed) ? null : parsed
}

function extractBrand(): string | null {
  return document.querySelector("#bylineInfo")?.textContent?.replace(/^(Visit the|Brand:|by)\s*/i, "").trim() ?? null
}

function extractAvailability(): string {
  const el = document.getElementById("availability")
  const text = el?.textContent?.trim().toLowerCase() ?? ""
  if (text.includes("in stock")) return "in_stock"
  if (text.includes("out of stock")) return "out_of_stock"
  return "unknown"
}

function extractImageUrl(): string | null {
  const img = document.getElementById("landingImage") as HTMLImageElement | null
  return img?.src ?? null
}

async function run() {
  const url = window.location.href
  const asin = extractAsin(url)
  const title = extractTitle()
  const price = extractPrice()

  // Can't proceed without these three
  if (!asin || !title || !price) {
    chrome.storage.local.set({
      omni_result: { error: true, message: "Could not extract product data from this page." },
    })
    return
  }

  chrome.storage.local.set({ omni_result: { loading: true } })

  try {
    const result = await analyzeProduct({
      retailer: "amazon",
      product_url: url,
      title,
      price,
      currency: "USD",
      availability: extractAvailability(),
      image_url: extractImageUrl() ?? undefined,
      brand: extractBrand() ?? undefined,
      retailer_product_id: asin,
    })

    chrome.storage.local.set({ omni_result: { loading: false, data: result } })
  } catch (err: any) {
    chrome.storage.local.set({
      omni_result: { loading: false, error: true, message: err.message ?? "Backend error" },
    })
  }
}

run()
