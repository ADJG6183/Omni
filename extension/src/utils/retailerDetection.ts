export type SupportedRetailer = "amazon"

export function detectRetailer(url: string): SupportedRetailer | null {
  if (/amazon\.com\/(?:dp|gp\/product)\/[A-Z0-9]{10}/i.test(url)) {
    return "amazon"
  }
  return null
}

export function isProductPage(url: string): boolean {
  return detectRetailer(url) !== null
}
