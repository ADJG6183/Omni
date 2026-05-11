const API_BASE = "http://localhost:8000"

export interface ProductObservation {
  retailer: string
  product_url: string
  title: string
  price: number
  currency: string
  availability?: string
  image_url?: string
  brand?: string
  category?: string
  retailer_product_id?: string
}

export interface AnalysisResponse {
  product_id: string
  recommendation: string
  recommendation_label: string
  confidence: string
  drop_probability_7d: number | null
  current_price: number
  average_price_30d: number | null
  lowest_price_seen: number | null
  highest_price_seen: number | null
  explanation: string[]
  price_history_available: boolean
  model_version: string
  latency_ms: number | null
}

export async function analyzeProduct(observation: ProductObservation): Promise<AnalysisResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/products/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(observation),
  })

  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ message: "Unknown error" }))
    throw new Error(error.message ?? `API error ${resp.status}`)
  }

  return resp.json()
}
