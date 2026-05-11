import { useEffect, useState } from "react"
import { RecommendationCard } from "./components/RecommendationCard"
import type { AnalysisResponse } from "./utils/apiClient"

type StoredResult =
  | { loading: true }
  | { loading: false; data: AnalysisResponse }
  | { error: true; message: string }
  | null

export default function Popup() {
  const [result, setResult] = useState<StoredResult>(null)

  useEffect(() => {
    chrome.storage.local.get("omni_result", (items) => {
      setResult(items.omni_result ?? null)
    })

    // Listen for updates while popup is open
    const listener = (changes: Record<string, chrome.storage.StorageChange>) => {
      if (changes.omni_result) {
        setResult(changes.omni_result.newValue)
      }
    }
    chrome.storage.onChanged.addListener(listener)
    return () => chrome.storage.onChanged.removeListener(listener)
  }, [])

  return (
    <div style={{ minWidth: 320, padding: 8 }}>
      <Header />
      <Body result={result} />
    </div>
  )
}

function Header() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        paddingBottom: 10,
        borderBottom: "1px solid #e5e7eb",
        marginBottom: 10,
      }}>
      <span style={{ fontWeight: 800, fontSize: 16, color: "#111827" }}>Omni</span>
      <span style={{ fontSize: 11, color: "#6b7280" }}>AI Price Intelligence</span>
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
    return (
      <Placeholder
        message={(result as any).message ?? "Something went wrong. Try refreshing the page."}
        isError
      />
    )
  }

  if ("data" in result) {
    return <RecommendationCard data={result.data} />
  }

  return <Placeholder message="No product detected on this page." />
}

function Placeholder({
  message,
  spinner = false,
  isError = false,
}: {
  message: string
  spinner?: boolean
  isError?: boolean
}) {
  return (
    <div
      style={{
        padding: "20px 16px",
        textAlign: "center",
        color: isError ? "#dc2626" : "#6b7280",
        fontSize: 13,
      }}>
      {spinner && (
        <div
          style={{
            width: 20,
            height: 20,
            border: "2px solid #e5e7eb",
            borderTop: "2px solid #2563eb",
            borderRadius: "50%",
            margin: "0 auto 10px",
            animation: "spin 0.8s linear infinite",
          }}
        />
      )}
      {message}
    </div>
  )
}
