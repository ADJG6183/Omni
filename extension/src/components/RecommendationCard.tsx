import "./recommendation.css"
import type { AnalysisResponse } from "../utils/apiClient"

const VERDICT_CLASS: Record<string, string> = {
  BUY_NOW: "card-verdict--buy-now",
  WAIT_FOR_DROP: "card-verdict--wait-for-drop",
  WATCH_CLOSELY: "card-verdict--watch-closely",
  AVOID_THIS_DEAL: "card-verdict--avoid",
}

function fmt(n: number | null | undefined): string {
  return n == null ? "—" : `$${n.toFixed(2)}`
}

interface Props {
  data: AnalysisResponse
  extractionWarnings: string[]
}

export function RecommendationCard({ data, extractionWarnings }: Props) {
  const verdictClass = VERDICT_CLASS[data.recommendation] ?? ""
  const allWarnings = [...extractionWarnings, ...data.warnings]

  return (
    <div className="card-root">
      <div className="card-eyebrow">Omni Verdict</div>

      <div className={`card-verdict ${verdictClass}`}>
        {data.recommendation_label}
      </div>

      <div className="card-prices">
        <span className="card-price-label">Current</span>
        <span className="card-price-value">{fmt(data.current_price)}</span>
        <span className="card-price-label">30d Average</span>
        <span className="card-price-value">{fmt(data.average_price_30d)}</span>
        <span className="card-price-label">Lowest Seen</span>
        <span className="card-price-value">{fmt(data.lowest_price_seen)}</span>
        <span className="card-price-label">Highest Seen</span>
        <span className="card-price-value">{fmt(data.highest_price_seen)}</span>
      </div>

      <div className="card-section-title">Why Omni says this:</div>
      <ul className="card-explanation">
        {data.explanation.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>

      {allWarnings.length > 0 && (
        <div className="card-warnings">
          <div className="card-warnings-title">⚠ Data quality notices</div>
          <ul className="card-warnings-list">
            {allWarnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card-footer">
        Confidence: {data.confidence} · {data.model_version}
      </div>
    </div>
  )
}
