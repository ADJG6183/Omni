import { useEffect, useState } from "react"
import "./popup.css"
import { RecommendationCard } from "./components/RecommendationCard"
import type { AnalysisResponse } from "./utils/apiClient"

import logoUrl from "url:../assets/icon48.png"

type StoredResult =
  | { loading: true; asin: string | null }
  | { loading: false; asin: string; data: AnalysisResponse; extractionWarnings: string[] }
  | { error: true; code: string; message: string; asin: string | null }
  | null

function extractAsinFromUrl(url: string): string | null {
  const match = url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/)
  return match ? match[1] : null
}

export default function Popup() {
  const [result, setResult] = useState<StoredResult>(null)
  const [tabAsin, setTabAsin] = useState<string | null>(null)

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      setTabAsin(extractAsinFromUrl(tabs[0]?.url ?? ""))
    })

    chrome.storage.local.get("omni_result", (items) => {
      setResult(items.omni_result ?? null)
    })

    const listener = (changes: Record<string, chrome.storage.StorageChange>) => {
      if (changes.omni_result) setResult(changes.omni_result.newValue)
    }
    chrome.storage.onChanged.addListener(listener)
    return () => chrome.storage.onChanged.removeListener(listener)
  }, [])

  const storedAsin = result && "asin" in result ? result.asin : null
  const isStale = tabAsin && storedAsin && tabAsin !== storedAsin

  return (
    <div className="popup-root">
      <Header />
      {isStale && (
        <div className="popup-stale-banner">
          ⚠ Omni is analyzing this page. Results from the previous product are shown below.
        </div>
      )}
      <Body result={result} />
    </div>
  )
}

function Header() {
  return (
    <div className="popup-header">
      <img src={logoUrl} className="popup-header-logo" alt="Omni logo" />
      <div className="popup-header-text">
        <span className="popup-header-title">Omni</span>
        <span className="popup-header-sub">AI Price Intelligence</span>
      </div>
    </div>
  )
}

function Body({ result }: { result: StoredResult }) {
  if (!result) {
    return <Placeholder message="Visit an Amazon product page to get a recommendation." />
  }
  if ("loading" in result && result.loading) {
    return <Placeholder message="Analyzing price history…" spinner />
  }
  if ("error" in result && result.error) {
    const r = result as { error: true; code: string; message: string }
    return <ErrorState code={r.code} message={r.message} />
  }
  if ("data" in result) {
    return (
      <RecommendationCard
        data={result.data}
        extractionWarnings={result.extractionWarnings ?? []}
      />
    )
  }
  return <Placeholder message="No product detected on this page." />
}

const ERROR_LABELS: Record<string, string> = {
  ASIN_NOT_FOUND: "Product not identified",
  TITLE_NOT_FOUND: "Title unavailable",
  PRICE_NOT_FOUND: "Price unavailable",
  API_ERROR: "Backend unreachable",
}

function ErrorState({ code, message }: { code: string; message: string }) {
  return (
    <div className="popup-error">
      <div className="popup-error-badge">{ERROR_LABELS[code] ?? "Error"}</div>
      <div className="popup-error-message">{message}</div>
    </div>
  )
}

function Placeholder({ message, spinner = false }: { message: string; spinner?: boolean }) {
  return (
    <div className="popup-placeholder">
      {spinner && <div className="popup-spinner" />}
      {message}
    </div>
  )
}
