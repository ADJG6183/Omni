# Omni — AI Price Intelligence Assistant

## 1. Product Overview

### Product Name

**Omni**

### Full Project Title

**Omni: AI Price Intelligence Assistant**

### One-Line Description

Omni is an AI-powered Chrome extension and backend ML system that helps online shoppers decide whether to buy, wait, watch, or avoid a product by tracking prices, predicting future price drops, and generating explainable shopping recommendations.

### Product Positioning

Omni is not just a price tracker. It is a real-time shopping intelligence layer that appears while users are browsing online stores and provides a clear recommendation based on historical price behavior, product metadata, retailer patterns, user preferences, and ML-based price-drop prediction.

### Core User Question

> “Should I buy this product now, wait for a better price, or avoid it?”

### Main Output

For each supported product page, Omni should produce:

* Current product price
* Historical price context
* Price trend visualization
* Probability of a meaningful price drop
* Buy / Wait / Watch / Avoid recommendation
* Explanation for the recommendation
* Optional target price tracking
* Optional price drop alert

---

## 2. MVP Scope

### Primary Interface

**Google Chrome extension**

The Chrome extension is the main user-facing product because users need advice while actively shopping. A standalone web app can be added later as a dashboard, but the MVP should prioritize in-browser decision support.

### Secondary Interface

**Backend API + optional admin/developer dashboard**

The backend should handle product normalization, price history storage, feature engineering, model inference, recommendation logic, logging, monitoring, and user watchlists.

### MVP Retailers

Start with a narrow retailer set to keep extraction logic manageable:

1. Amazon
2. Best Buy

If one of these becomes too restrictive due to scraping or DOM instability, fallback to:

* Walmart
* Target
* eBay
* Manual product entry
* API-based product lookup

### MVP Category

Start with **electronics**, because electronics often have meaningful price movement, clear product metadata, user purchase sensitivity, and comparison-shopping behavior.

Example MVP products:

* Headphones
* Keyboards
* Monitors
* Gaming mice
* Smartwatches
* Speakers
* External SSDs
* Routers

### MVP Recommendation Labels

Use four user-friendly labels:

* **Buy Now**
* **Wait for Drop**
* **Watch Closely**
* **Avoid This Deal**

### MVP ML Objective

Predict whether a product will experience a meaningful price drop within the next 7 days.

Recommended binary classification target:

```text
Target = 1 if product price drops by >= 5% within the next 7 days
Target = 0 otherwise
```

The threshold should be configurable by category. For example, a 5% drop may matter for electronics, but beauty products or low-cost items may need a different threshold.

---

## 3. Product Goals

### User Goals

Users should be able to:

1. Browse supported product pages normally.
2. See Omni’s recommendation without leaving the page.
3. Understand whether the current price is good or bad.
4. Track products they care about.
5. Set a target price.
6. Receive an alert when a tracked product reaches a desired price.
7. Understand why Omni recommends buying, waiting, watching, or avoiding.

### Engineering Goals

The system should:

1. Extract product data reliably from supported retailers.
2. Normalize product identities across sessions and retailers where possible.
3. Store historical price observations cleanly.
4. Run ML inference with low latency.
5. Avoid blocking the browser experience.
6. Handle missing, malformed, duplicate, or suspicious product data.
7. Provide fallback recommendations when ML confidence is low.
8. Log enough information for debugging and ML monitoring.
9. Support testable, modular backend logic.
10. Be structured so new retailers and product categories can be added later.

### ML Goals

The ML system should:

1. Collect clean historical price data.
2. Perform EDA to understand pricing behavior.
3. Engineer features from time, price history, retailer behavior, product category, and user preferences.
4. Train a baseline model first.
5. Train stronger tree-based models after baseline.
6. Evaluate with classification metrics and business-oriented metrics.
7. Serve predictions through an API.
8. Track prediction confidence and model drift.
9. Support retraining as more data is collected.
10. Use explainability techniques to justify recommendations.

---

## 4. High-Level Architecture

### Recommended MVP Architecture

```text
Chrome Extension
  - Content script extracts product data from retailer pages
  - Popup UI displays recommendation
  - Background worker manages API calls and cached state
  - Optional in-page floating widget

FastAPI Backend
  - Receives product observations
  - Normalizes product identity
  - Stores price history
  - Builds feature vectors
  - Calls ML inference service/module
  - Applies recommendation rules
  - Returns response to extension

PostgreSQL Database
  - Users
  - Products
  - Retailers
  - Price history
  - Watchlists
  - Predictions
  - Alerts
  - Model metadata
  - Logs/events

ML Pipeline
  - Data validation
  - EDA notebooks/scripts
  - Feature engineering
  - Training pipeline
  - Evaluation
  - Model registry/versioning
  - Batch retraining

Scheduler / Worker
  - Periodically refreshes tracked product prices
  - Runs feature generation jobs
  - Triggers alert checks
  - Supports model retraining jobs

Notification Layer
  - Browser notifications for MVP
  - Email alerts as stretch
  - SMS as stretch

Deployment
  - Backend: Google Cloud Run
  - Database: Cloud SQL PostgreSQL or Supabase
  - Scheduler: Cloud Scheduler or cron-based worker
  - Containerization: Docker
  - CI/CD: GitHub Actions
```

---

## 5. System Components

## 5.1 Chrome Extension

### Responsibilities

The Chrome extension should:

1. Detect whether the user is on a supported product page.
2. Extract product information from the DOM.
3. Send product information to the backend.
4. Display Omni’s recommendation.
5. Let user track the product.
6. Let user set target price.
7. Show price history and explanation.
8. Cache recent responses to reduce latency and API load.

### Extension Parts

```text
extension/
  manifest.json
  src/
    background/
      background.ts
    content/
      contentScript.ts
      extractors/
        amazonExtractor.ts
        bestBuyExtractor.ts
        baseExtractor.ts
    popup/
      Popup.tsx
      popup.css
    components/
      RecommendationCard.tsx
      PriceHistoryChart.tsx
      TrackButton.tsx
    utils/
      apiClient.ts
      retailerDetection.ts
      cache.ts
```

### Recommended Extension Stack

Preferred:

```text
Plasmo + React + TypeScript
```

Alternative simpler MVP:

```text
Vanilla JavaScript + HTML + CSS Chrome Extension Manifest V3
```

### Product Data Extracted by Extension

Minimum required:

```json
{
  "retailer": "amazon",
  "product_url": "https://...",
  "canonical_url": "https://...",
  "title": "Sony WH-1000XM5 Wireless Headphones",
  "price": 328.00,
  "currency": "USD",
  "image_url": "https://...",
  "availability": "in_stock",
  "timestamp": "2026-05-09T17:00:00-04:00"
}
```

Optional but useful:

```json
{
  "brand": "Sony",
  "rating": 4.6,
  "review_count": 18342,
  "seller": "Amazon.com",
  "shipping_cost": 0.00,
  "discount_percent_displayed": 12,
  "list_price": 399.99,
  "category": "electronics",
  "retailer_product_id": "B09XS7JWHH"
}
```

### Extension UX States

The UI should handle these states:

1. Supported product page detected.
2. Unsupported page.
3. Product detected but price missing.
4. Backend loading.
5. Recommendation available.
6. Product already tracked.
7. Product added to watchlist.
8. Backend error.
9. Low confidence recommendation.
10. Insufficient price history.

### Example Extension UI

```text
Omni Verdict: Wait for Drop

Current Price: $328.00
Lowest Seen: $278.00
Average Price: $342.00
7-Day Drop Probability: 68%

Why Omni says wait:
- Current price is 18% above historical low
- Product has dropped twice in the last 30 days
- Similar electronics often dip near weekends
- Model confidence: Medium

[Track Product]
[Set Target Price]
[View History]
```

---

## 5.2 Backend API

### Recommended Backend Stack

```text
Python
FastAPI
Pydantic
SQLAlchemy or SQLModel
PostgreSQL
Alembic migrations
Redis optional for caching
pytest for testing
Docker for deployment
```

### Backend Responsibilities

The backend should:

1. Receive product observations from the extension.
2. Validate incoming data.
3. Normalize product URLs and product identities.
4. Create or update product records.
5. Store price observations.
6. Generate features for prediction.
7. Call the ML model.
8. Apply recommendation logic.
9. Return structured response.
10. Log all important events.
11. Support watchlist and alert workflows.
12. Handle edge cases gracefully.

### API Endpoints

#### Health Check

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "service": "omni-api",
  "version": "0.1.0"
}
```

#### Analyze Product

```http
POST /api/v1/products/analyze
```

Purpose:
Receive product data from the extension, store the observation, generate prediction, and return recommendation.

Request:

```json
{
  "retailer": "amazon",
  "product_url": "https://www.amazon.com/dp/B09XS7JWHH",
  "title": "Sony WH-1000XM5 Wireless Headphones",
  "price": 328.00,
  "currency": "USD",
  "image_url": "https://...",
  "availability": "in_stock",
  "brand": "Sony",
  "rating": 4.6,
  "review_count": 18342,
  "category": "electronics",
  "timestamp": "2026-05-09T17:00:00-04:00"
}
```

Response:

```json
{
  "product_id": "uuid",
  "recommendation": "WAIT_FOR_DROP",
  "recommendation_label": "Wait for Drop",
  "confidence": "medium",
  "drop_probability_7d": 0.68,
  "current_price": 328.00,
  "average_price_30d": 342.00,
  "lowest_price_seen": 278.00,
  "highest_price_seen": 399.99,
  "predicted_price_range_7d": {
    "low": 289.00,
    "high": 315.00
  },
  "explanation": [
    "Current price is above the historical low.",
    "The product has shown recent price volatility.",
    "The model predicts a strong chance of a price drop within 7 days."
  ],
  "price_history_available": true,
  "model_version": "price_drop_xgb_v1",
  "latency_ms": 132
}
```

#### Add Product to Watchlist

```http
POST /api/v1/watchlist
```

Request:

```json
{
  "user_id": "uuid",
  "product_id": "uuid",
  "target_price": 275.00,
  "urgency": "low",
  "notify": true
}
```

#### Get Watchlist

```http
GET /api/v1/watchlist/{user_id}
```

#### Get Product Price History

```http
GET /api/v1/products/{product_id}/history
```

#### Get Product Prediction

```http
GET /api/v1/products/{product_id}/prediction
```

#### Manual Product Search or Entry

```http
POST /api/v1/products/manual
```

This is useful when product extraction fails or when a user wants to paste a product URL manually.

---

## 6. Database Design

### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### retailers

```sql
CREATE TABLE retailers (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    is_supported BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### products

```sql
CREATE TABLE products (
    id UUID PRIMARY KEY,
    retailer_id UUID REFERENCES retailers(id),
    retailer_product_id TEXT,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    image_url TEXT,
    normalized_title TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(retailer_id, retailer_product_id)
);
```

### price_history

```sql
CREATE TABLE price_history (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    price NUMERIC(10, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    availability TEXT,
    shipping_cost NUMERIC(10, 2),
    observed_at TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### product_metadata_snapshots

```sql
CREATE TABLE product_metadata_snapshots (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    rating NUMERIC(3, 2),
    review_count INTEGER,
    seller TEXT,
    list_price NUMERIC(10, 2),
    discount_percent_displayed NUMERIC(5, 2),
    availability TEXT,
    observed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### watchlists

```sql
CREATE TABLE watchlists (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    product_id UUID REFERENCES products(id),
    target_price NUMERIC(10, 2),
    urgency TEXT DEFAULT 'medium',
    notify BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, product_id)
);
```

### predictions

```sql
CREATE TABLE predictions (
    id UUID PRIMARY KEY,
    product_id UUID REFERENCES products(id),
    model_version TEXT NOT NULL,
    drop_probability_7d NUMERIC(5, 4),
    predicted_price_low_7d NUMERIC(10, 2),
    predicted_price_high_7d NUMERIC(10, 2),
    recommendation TEXT NOT NULL,
    confidence TEXT NOT NULL,
    explanation JSONB,
    feature_snapshot JSONB,
    predicted_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### alerts

```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    product_id UUID REFERENCES products(id),
    alert_type TEXT NOT NULL,
    threshold_price NUMERIC(10, 2),
    triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### model_registry

```sql
CREATE TABLE model_registry (
    id UUID PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL UNIQUE,
    model_type TEXT NOT NULL,
    training_data_start TIMESTAMP,
    training_data_end TIMESTAMP,
    metrics JSONB,
    artifact_path TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 7. Data Handling Strategy

Data handling is one of the most important parts of Omni. The project should be designed as a real ML lifecycle system, not just a frontend app calling a model.

### 7.1 Data Sources

Potential data sources:

1. Chrome extension observations from product pages.
2. Scheduled re-checks of tracked products.
3. External product APIs where available.
4. Manually seeded product price histories.
5. Public datasets for bootstrapping.
6. Simulated price history for early development.

### 7.2 Data Ingestion Principles

All incoming product observations should be treated as raw, imperfect data.

Backend should validate:

* Product URL exists
* Retailer is supported
* Title is non-empty
* Price is numeric
* Price is positive
* Currency is supported
* Timestamp is valid
* Availability is standardized
* Duplicate observations are handled
* Suspicious price jumps are flagged

### 7.3 Raw vs Processed Data

Keep raw and processed layers conceptually separate.

Recommended layers:

```text
Raw observation
  - Exactly what extension/API captured

Validated observation
  - Cleaned and schema-validated

Normalized product record
  - Product identity resolved

Feature table
  - ML-ready feature vector

Prediction output
  - Model score + recommendation
```

### 7.4 Product Identity Normalization

Product matching is difficult. Different URLs may represent the same product.

Use:

* Retailer product ID when available
* Canonical URL normalization
* URL path cleaning
* Query parameter removal
* Normalized title
* Brand + title similarity
* Optional embedding-based similarity later

For MVP, use retailer-specific IDs when available.

Examples:

Amazon:

```text
https://www.amazon.com/dp/B09XS7JWHH
```

Extract:

```text
retailer_product_id = B09XS7JWHH
```

Best Buy:

```text
skuId = 6505727
```

Extract:

```text
retailer_product_id = 6505727
```

### 7.5 Price Observation Rules

Do not store every identical price observation if it creates noise. Recommended logic:

* Store observation if price changed.
* Store observation if availability changed.
* Store observation if last observation is older than a configured interval.
* Avoid storing duplicate observations within a short time window.

Example:

```text
If same product, same price, same availability, and observed within last 6 hours:
    Do not insert duplicate price row.
Else:
    Insert new price observation.
```

### 7.6 Data Quality Checks

Implement checks for:

* Negative prices
* Zero prices
* Missing title
* Missing URL
* Currency mismatch
* Price jumps greater than 80% in one observation
* Repeated identical timestamps
* Non-USD currency during MVP
* Product title changing significantly
* Duplicate product records
* Availability conflict

Suspicious data should not always be discarded. Some should be flagged for review.

### 7.7 Missing Data Handling

Missing values should be handled deliberately:

* Missing rating: store null, impute only for ML if needed.
* Missing review count: store null.
* Missing brand: infer from title later if possible.
* Missing category: default to unknown, but do not train category-specific models on unknown category unless enough data exists.
* Missing price: do not create price observation, return frontend error state.
* Missing image: acceptable.

---

## 8. EDA Requirements

EDA should be treated as a first-class part of the project. Before training the model, the system should include scripts or notebooks that analyze the collected data.

### 8.1 EDA Goals

The EDA should answer:

1. How often do prices change?
2. Which retailers show the most price volatility?
3. Which categories have the most meaningful drops?
4. What is the typical size of a price drop?
5. How many days usually pass between drops?
6. Are there weekly or monthly seasonality patterns?
7. Are discounts more common on weekends?
8. Are higher-rated or more-reviewed products less volatile?
9. How often does a product hit a new historical low?
10. Is the 5% threshold reasonable for the selected category?

### 8.2 EDA Outputs

Create EDA scripts that generate:

* Price distribution by category
* Price change distribution
* Drop frequency by retailer
* Drop frequency by weekday
* Average discount percentage
* Number of observations per product
* Missing value report
* Outlier report
* Correlation matrix for numerical features
* Feature-target relationship analysis
* Class balance report
* Baseline target rate

### 8.3 EDA Directory

Recommended structure:

```text
ml/
  notebooks/
    01_data_quality_eda.ipynb
    02_price_behavior_eda.ipynb
    03_feature_target_analysis.ipynb
  reports/
    eda_summary.md
    data_quality_report.md
```

### 8.4 EDA Summary Template

Each EDA run should produce a short markdown summary:

```text
Dataset Summary
- Number of products:
- Number of price observations:
- Date range:
- Retailers:
- Categories:

Data Quality
- Missing price rows:
- Duplicate observations:
- Suspicious outliers:
- Products with insufficient history:

Target Analysis
- Positive class rate:
- Negative class rate:
- Recommended target threshold:

Feature Insights
- Most predictive features:
- Weak features:
- Potential leakage risks:

Next Actions
- Data cleaning needed:
- Features to add:
- Modeling concerns:
```

---

## 9. Feature Engineering

### 9.1 Core Feature Groups

#### Current Price Features

```text
current_price
current_price_log
current_price_vs_list_price_pct
current_price_vs_avg_7d_pct
current_price_vs_avg_14d_pct
current_price_vs_avg_30d_pct
current_price_vs_min_30d_pct
current_price_vs_max_30d_pct
```

#### Rolling Price Features

```text
price_avg_3d
price_avg_7d
price_avg_14d
price_avg_30d
price_min_7d
price_min_30d
price_max_7d
price_max_30d
price_std_7d
price_std_30d
price_median_30d
```

#### Price Movement Features

```text
price_change_1d
price_change_3d
price_change_7d
price_change_pct_1d
price_change_pct_3d
price_change_pct_7d
num_price_drops_7d
num_price_drops_30d
num_price_increases_7d
num_price_increases_30d
days_since_last_drop
days_since_last_increase
```

#### Volatility Features

```text
price_volatility_7d
price_volatility_30d
coefficient_of_variation_30d
range_30d
range_pct_30d
```

#### Retailer/Product Features

```text
retailer
brand
category
rating
review_count
availability
shipping_cost
seller
```

#### Time Features

```text
day_of_week
is_weekend
month
week_of_year
is_holiday_season
is_black_friday_window
is_cyber_monday_window
is_back_to_school_window
is_end_of_month
```

#### User Features

```text
target_price
current_price_vs_target_pct
urgency_level
```

### 9.2 Label Creation

For each product observation at time `t`, define label:

```text
future_min_price_7d = minimum observed product price from t+1 to t+7 days
price_drop_pct_7d = (current_price - future_min_price_7d) / current_price
label_drop_7d = 1 if price_drop_pct_7d >= 0.05 else 0
```

Important: Avoid leakage.

Do not use future data in features. Future data should only be used to create labels.

### 9.3 Leakage Risks

Avoid these leakage problems:

* Using future prices in rolling averages.
* Randomly splitting rows from the same product across train/test without respecting time.
* Using labels created from future windows as features.
* Using current displayed discount if it directly reveals the future promotion window.
* Training and evaluating on duplicate observations.

### 9.4 Minimum Data Requirements

For ML prediction, require at least:

```text
Minimum product history for reliable ML: 7 days
Preferred product history: 30 days
Strong product history: 90 days
```

If insufficient history exists, use fallback logic:

```text
If product has less than 7 days of price history:
    Use category-level and retailer-level heuristics.
    Return low confidence.
```

---

## 10. Machine Learning Lifecycle

## 10.1 ML Development Stages

### Stage 1 — Simulated / Seed Data

Use generated or manually collected price data to build the full pipeline before real data volume exists.

Goals:

* Validate database design
* Validate feature generation
* Validate API responses
* Validate extension/backend flow
* Train dummy baseline model

### Stage 2 — Historical Observations

Collect real product price observations for a small number of electronics products.

Goals:

* Run EDA
* Identify data quality problems
* Tune target threshold
* Build baseline model

### Stage 3 — Baseline Model

Train simple models:

* Logistic Regression
* Decision Tree
* Random Forest

Goals:

* Establish baseline performance
* Understand feature importance
* Create first production-compatible model

### Stage 4 — Strong Tabular Model

Train:

* XGBoost
* LightGBM
* CatBoost if categorical features become important

Goals:

* Improve prediction quality
* Compare against baseline
* Tune hyperparameters

### Stage 5 — Monitoring and Retraining

Track model performance over time.

Goals:

* Detect data drift
* Detect prediction drift
* Retrain when new data is available
* Version models cleanly

---

## 10.2 Recommended Models

### Baseline Model

```text
Logistic Regression
```

Purpose:

* Simple benchmark
* Easy to debug
* Helps understand if the task is learnable

### MVP Production Model

```text
Random Forest Classifier
```

Purpose:

* Handles nonlinear behavior
* Works well with tabular features
* Robust for early-stage data
* Easy feature importance

### Stronger Model

```text
XGBoost Classifier
```

Purpose:

* Strong performance on tabular data
* Handles mixed feature types after encoding
* Good for production ML portfolio story

### Stretch Time-Series Models

Use later only after enough per-product history exists:

* Prophet
* ARIMA
* LSTM
* Temporal Fusion Transformer

Do not start with deep learning. The MVP should prioritize strong feature engineering and clean lifecycle design.

---

## 10.3 Model Evaluation

### Classification Metrics

Track:

```text
accuracy
precision
recall
f1_score
roc_auc
pr_auc
confusion_matrix
calibration_curve
```

Precision and recall matter more than accuracy.

Reason:

* False Buy recommendation can hurt user trust.
* False Wait recommendation may cause users to miss a good deal.

### Business Metrics

Track:

```text
average_savings_opportunity
buy_now_success_rate
wait_recommendation_success_rate
missed_deal_rate
false_wait_rate
false_buy_rate
recommendation_coverage
```

Definitions:

```text
wait_recommendation_success_rate = percentage of Wait recommendations where price actually dropped meaningfully within prediction window

false_buy_rate = percentage of Buy recommendations where price dropped meaningfully shortly after

recommendation_coverage = percentage of analyzed products where system can return recommendation above minimum confidence
```

### Confidence Calibration

The model should not just output probability blindly. Probabilities should be calibrated if possible.

Recommended:

* CalibratedClassifierCV for sklearn models
* Reliability curves
* Probability buckets

Example:

```text
When model says 70% drop probability, actual drop rate should be close to 70% over many examples.
```

---

## 10.4 Model Artifacts

Store model artifacts as versioned files:

```text
ml/artifacts/
  price_drop_rf_v1.pkl
  price_drop_xgb_v1.pkl
  feature_columns_v1.json
  preprocessing_pipeline_v1.pkl
  metrics_v1.json
```

Use a model registry table in the database to track active model versions.

---

## 10.5 Model Serving

For MVP, model serving can happen inside the FastAPI backend process.

Latency-friendly approach:

1. Load model once at app startup.
2. Keep model in memory.
3. Build features quickly from database summary values.
4. Avoid running expensive EDA or retraining during request time.
5. Cache recent product predictions.

Do not load the model from disk on every request.

Recommended request-time logic:

```text
API receives product observation
↓
Validate data
↓
Store observation
↓
Fetch recent price summary from database
↓
Build feature vector
↓
Run in-memory model inference
↓
Apply recommendation rules
↓
Return result
```

---

## 11. Recommendation Engine

The recommendation engine should combine ML prediction with deterministic business rules.

### 11.1 Recommendation Inputs

```text
drop_probability_7d
current_price
lowest_price_seen
average_price_30d
price_volatility_30d
user_target_price
user_urgency
availability
model_confidence
price_history_length
```

### 11.2 Recommendation Labels

Internal enum:

```text
BUY_NOW
WAIT_FOR_DROP
WATCH_CLOSELY
AVOID_THIS_DEAL
INSUFFICIENT_DATA
```

User-facing labels:

```text
Buy Now
Wait for Drop
Watch Closely
Avoid This Deal
Not Enough Data Yet
```

### 11.3 Example Recommendation Rules

```text
If availability == out_of_stock:
    recommendation = WATCH_CLOSELY

If price_history_length < 7 days:
    recommendation = INSUFFICIENT_DATA or WATCH_CLOSELY
    confidence = low

If current_price <= user_target_price:
    recommendation = BUY_NOW

If drop_probability_7d >= 0.70 and current_price > lowest_price_seen * 1.05:
    recommendation = WAIT_FOR_DROP

If current_price <= lowest_price_seen * 1.03 and drop_probability_7d < 0.50:
    recommendation = BUY_NOW

If current_price > average_price_30d * 1.15:
    recommendation = AVOID_THIS_DEAL

Else:
    recommendation = WATCH_CLOSELY
```

### 11.4 Explanation Generation

Explanation should be template-based for MVP, not LLM-based.

Good explanation examples:

```text
Current price is near the lowest observed price.
The model predicts a low chance of a further drop soon.
This is likely a good time to buy.
```

```text
Current price is above the product's recent average.
The product has had multiple price drops in the last 30 days.
The model predicts a high chance of another drop within 7 days.
```

```text
Omni has limited price history for this product.
The recommendation is based on retailer and category-level patterns.
Confidence is low until more data is collected.
```

---

## 12. Latency and Performance Requirements

Latency matters because the extension appears while the user is shopping.

### 12.1 Latency Targets

```text
Extension product detection: < 300 ms after page load settles
Backend analyze API p50 latency: < 300 ms
Backend analyze API p95 latency: < 1000 ms
Extension full recommendation display: < 2 seconds
Cached recommendation display: < 300 ms
```

### 12.2 Latency Best Practices

Backend:

* Load ML model at startup.
* Cache product summaries.
* Use indexed database queries.
* Precompute rolling features when possible.
* Avoid expensive joins in hot API path.
* Use async FastAPI endpoints carefully.
* Keep response payloads small.
* Return fallback result if model inference fails.

Database:

* Index `products.retailer_product_id`.
* Index `price_history.product_id`.
* Index `price_history.observed_at`.
* Use composite index on `(product_id, observed_at)`.
* Keep price history queries bounded by time window.

Extension:

* Debounce DOM extraction.
* Avoid repeatedly calling backend during page changes.
* Cache recommendation by canonical URL.
* Use MutationObserver carefully.
* Do not block page rendering.
* Show loading state immediately.

### 12.3 Caching Strategy

Cache recommendation results for a short period.

Example:

```text
If same canonical product URL was analyzed within last 30 minutes:
    Show cached recommendation first.
    Optionally refresh in background.
```

Backend cache keys:

```text
recommendation:{retailer}:{retailer_product_id}
price_summary:{product_id}:30d
```

Use Redis later if needed. For MVP, in-memory cache or database-level reuse is acceptable.

---

## 13. Backend Edge Cases and Error Handling

Backend logic must be defensive. Product page extraction and price data can be messy.

### 13.1 Input Validation Edge Cases

Handle:

* Missing price
* Price string includes symbols or commas
* Price is zero
* Price is negative
* Currency is unsupported
* Product URL is malformed
* Retailer is unsupported
* Title is missing
* Title is extremely short
* Timestamp is missing
* Timestamp is in the future
* Availability is unknown
* Product image missing
* Rating is outside valid range
* Review count is negative

Expected behavior:

* Return structured error for invalid required fields.
* Store partial metadata only when safe.
* Do not create product price history row without valid price.
* Do not crash API.

Example error response:

```json
{
  "error": true,
  "code": "PRICE_MISSING",
  "message": "Could not identify a valid product price on this page.",
  "recommendation": "UNAVAILABLE",
  "retryable": true
}
```

### 13.2 Product Matching Edge Cases

Handle:

* Same product with multiple URLs
* Product variants like color or size
* Bundle listings
* Used/refurbished products
* Marketplace sellers
* Product page redirects
* Sponsored listings
* Duplicate product records
* Title changes over time

MVP behavior:

* Treat different retailer product IDs as different products.
* Do not over-merge products unless ID match is clear.
* Store variant info if extractable.
* Flag ambiguous product identity.

### 13.3 Price Edge Cases

Handle:

* Sale price and list price both visible
* Coupon price not included in main price
* Price range instead of exact price
* Subscription price
* Used item price
* Out-of-stock item with old price
* Lightning deal price
* Shipping changes total cost
* Tax not included
* Price displayed in installments

MVP behavior:

* Use main displayed purchase price.
* Store list price separately.
* Store coupon text if available later.
* Do not include tax in MVP.
* Shipping can be stored if available but not required.

### 13.4 ML Inference Edge Cases

Handle:

* Model file missing
* Model version inactive
* Feature vector missing required columns
* Feature generation fails
* Product has insufficient history
* Model returns NaN
* Model probability outside 0-1 due to bug
* Prediction timeout

Expected behavior:

* Return rule-based fallback recommendation.
* Mark confidence as low.
* Log error with trace ID.
* Do not expose stack trace to frontend.

Example fallback:

```json
{
  "recommendation": "WATCH_CLOSELY",
  "confidence": "low",
  "drop_probability_7d": null,
  "explanation": [
    "Omni does not have enough reliable price history for this product yet.",
    "Track this product to improve future recommendations."
  ]
}
```

### 13.5 Database Edge Cases

Handle:

* Duplicate inserts
* Race conditions from repeated extension calls
* Database unavailable
* Slow queries
* Migration mismatch
* Invalid UUID
* Foreign key violation

Expected behavior:

* Use idempotent upsert logic for products.
* Use transactions for product + price observation writes.
* Roll back cleanly on errors.
* Return useful error codes.
* Log database errors.

### 13.6 API Reliability Edge Cases

Handle:

* Request timeout
* Extension sends duplicate requests
* User refreshes page repeatedly
* Unsupported retailer
* CORS issues
* Invalid JSON
* API version mismatch

Expected behavior:

* Add request validation through Pydantic.
* Add rate limiting eventually.
* Use clear error codes.
* Include `trace_id` in error responses.

---

## 14. Testing Strategy

Testing should cover extension logic, backend logic, data pipeline, ML pipeline, and integration workflows.

## 14.1 Backend Unit Tests

Test:

* Product validation
* URL normalization
* Retailer product ID extraction
* Price parsing
* Product upsert logic
* Price history insert rules
* Feature generation
* Recommendation rules
* Error response generation

Example test cases:

```text
test_parse_amazon_product_id
test_parse_bestbuy_sku
test_reject_negative_price
test_reject_missing_title
test_deduplicate_same_price_observation
test_generate_features_with_30d_history
test_fallback_when_insufficient_history
test_recommend_buy_now_when_price_near_historical_low
test_recommend_wait_when_drop_probability_high
```

## 14.2 API Tests

Test:

* `GET /health`
* `POST /products/analyze` with valid data
* `POST /products/analyze` with missing price
* `POST /products/analyze` with unsupported retailer
* `POST /watchlist`
* `GET /products/{id}/history`

Use pytest + httpx TestClient.

## 14.3 Database Tests

Test:

* Product uniqueness constraints
* Price history inserts
* Watchlist uniqueness
* Prediction storage
* Transaction rollback

Use a test PostgreSQL database or SQLite only for limited local tests. Prefer PostgreSQL for realistic behavior.

## 14.4 ML Pipeline Tests

Test:

* Feature columns are generated consistently
* No future leakage in features
* Label creation works correctly
* Training script produces model artifact
* Model artifact can be loaded
* Model outputs valid probability
* Prediction schema is stable

Important test:

```text
Given price observations up to date T,
feature generation should only use data <= T.
```

## 14.5 Extension Tests

Test:

* Retailer detection
* Amazon product extraction
* Best Buy product extraction
* Missing price UI state
* API loading state
* Recommendation display
* Track product button
* Cached response behavior

For DOM extraction, use saved HTML fixtures.

Recommended structure:

```text
extension/tests/fixtures/
  amazon_product_page.html
  bestbuy_product_page.html
```

## 14.6 Integration Tests

End-to-end test:

```text
Simulated product page
↓
Extension extracts product data
↓
Backend analyze endpoint receives data
↓
Product and price observation are saved
↓
Feature vector is generated
↓
Model returns prediction
↓
Recommendation response is returned
↓
Extension displays result
```

## 14.7 CI/CD Testing

GitHub Actions should run:

```text
backend lint
backend unit tests
backend API tests
ML pipeline smoke test
extension build
extension unit tests
Docker build test
```

---

## 15. Security and Privacy

### 15.1 Data Minimization

The extension should only collect data needed for the product recommendation:

* Product URL
* Product title
* Price
* Retailer
* Product metadata
* Watchlist preferences

Do not collect:

* Full browsing history
* Payment info
* Checkout data
* Personal messages
* Cookies
* Passwords
* Unrelated page content

### 15.2 User Authentication

MVP can start without full authentication by using anonymous extension IDs.

Better version:

* Supabase Auth
* Firebase Auth
* Auth0
* Google OAuth

### 15.3 API Security

Implement:

* CORS restrictions
* API rate limits
* Input validation
* Request size limits
* Structured logs without sensitive data
* Environment variables for secrets
* HTTPS only

---

## 16. Monitoring and Observability

### 16.1 Backend Logs

Log:

* Request ID / trace ID
* Retailer
* Product ID
* API latency
* Feature generation latency
* Model inference latency
* Recommendation result
* Error code if any

Do not log sensitive user data unnecessarily.

### 16.2 ML Monitoring

Track:

* Prediction distribution
* Drop probability distribution
* Recommendation distribution
* Feature drift
* Missing feature rates
* Model confidence trends
* False buy rate
* False wait rate

### 16.3 Data Monitoring

Track:

* Number of observations per day
* Number of active products
* Products with stale prices
* Duplicate observation rate
* Failed extraction rate
* Unsupported page rate
* Suspicious price outlier rate

---

## 17. Suggested Repository Structure

```text
omni/
  README.md
  docker-compose.yml
  .env.example
  .github/
    workflows/
      ci.yml
  backend/
    app/
      main.py
      api/
        v1/
          routes_products.py
          routes_watchlist.py
          routes_health.py
      core/
        config.py
        logging.py
        errors.py
      db/
        session.py
        models.py
        migrations/
      schemas/
        product.py
        prediction.py
        watchlist.py
        errors.py
      services/
        product_service.py
        price_service.py
        feature_service.py
        prediction_service.py
        recommendation_service.py
        alert_service.py
      ml_runtime/
        model_loader.py
        predictor.py
      tests/
        unit/
        integration/
    Dockerfile
    pyproject.toml
  extension/
    manifest.json
    package.json
    src/
      background/
      content/
      popup/
      components/
      utils/
    tests/
      fixtures/
  ml/
    notebooks/
    src/
      data_validation.py
      build_features.py
      create_labels.py
      train.py
      evaluate.py
      registry.py
    artifacts/
    reports/
    tests/
  docs/
    architecture.md
    api_contract.md
    ml_lifecycle.md
    data_dictionary.md
    edge_cases.md
```

---

## 18. Development Roadmap

### Phase 1 — Foundation

Build:

* Backend FastAPI project
* PostgreSQL schema
* Product analyze endpoint
* Product and price history storage
* Basic recommendation rules
* Dummy model response
* Chrome extension proof of concept

Goal:

```text
User visits supported page → extension extracts product → backend stores price → backend returns basic recommendation.
```

### Phase 2 — Data Collection and EDA

Build:

* Real price observation storage
* Duplicate handling
* EDA notebooks
* Data quality reports
* Feature generation script
* Label creation logic

Goal:

```text
Collect enough product data to understand pricing behavior and create the first training dataset.
```

### Phase 3 — Baseline ML

Build:

* Logistic Regression baseline
* Random Forest model
* Evaluation scripts
* Model artifact saving/loading
* Prediction endpoint integration

Goal:

```text
Backend returns real ML-based drop probability and recommendation.
```

### Phase 4 — Improved ML and Explanations

Build:

* XGBoost model
* Feature importance
* Calibrated probabilities
* Better recommendation scoring
* Explanation templates

Goal:

```text
Omni produces more accurate and explainable recommendations.
```

### Phase 5 — Watchlist and Alerts

Build:

* User watchlist
* Target price settings
* Scheduled price checks
* Browser notifications
* Email alerts optional

Goal:

```text
User can track products and get notified when price reaches target.
```

### Phase 6 — Polish and Portfolio Readiness

Build:

* Clean extension UI
* Demo dataset
* Architecture diagrams
* README
* Model card
* EDA report
* Testing report
* Demo video

Goal:

```text
Project is ready for resume, GitHub, portfolio, and interviews.
```

---

## 19. Claude Code Build Instructions

Use this section as a direct implementation guide for Claude Code.

### Primary Goal

Build Omni as a production-style ML-backed Chrome extension and FastAPI backend. Prioritize clean architecture, data handling, testing, and ML lifecycle structure over quick hacks.

### Implementation Priorities

1. Create repository structure exactly or close to the structure defined above.
2. Build FastAPI backend with modular services.
3. Add PostgreSQL models and migrations.
4. Implement product analyze endpoint.
5. Implement robust validation and error handling.
6. Implement product URL normalization for Amazon and Best Buy.
7. Implement price history storage with duplicate handling.
8. Implement placeholder feature generation and recommendation engine.
9. Add ML module with baseline model loading interface.
10. Add tests for backend services.
11. Build Chrome extension MVP that extracts product title and price.
12. Connect extension to backend API.
13. Add EDA and ML pipeline scripts.
14. Add README and developer setup instructions.

### Coding Standards

* Use TypeScript for extension if possible.
* Use Python type hints everywhere in backend.
* Use Pydantic schemas for request/response validation.
* Keep business logic out of route files.
* Keep ML inference logic isolated from recommendation rules.
* Add docstrings for complex logic.
* Use environment variables for configuration.
* Never hardcode secrets.
* Add structured error responses.
* Add unit tests as features are built.

### Do Not Do

* Do not build the ML model before data schema and feature pipeline are defined.
* Do not scrape aggressively.
* Do not collect unrelated browsing data.
* Do not put all backend logic in `main.py`.
* Do not load model artifacts on every request.
* Do not ignore missing data cases.
* Do not return unexplained recommendations.
* Do not use future price data in ML features.

---

## 20. Resume / Portfolio Description

Use this later for resume or interviews:

```text
Built Omni, an AI-powered Chrome extension and backend ML system that analyzes online product pages in real time, tracks historical price behavior, predicts the likelihood of future price drops, and generates explainable buy/wait/avoid recommendations. Designed the full ML lifecycle including data ingestion, EDA, feature engineering, baseline modeling, XGBoost experimentation, model serving, latency-aware inference, backend error handling, and production-style testing.
```

---

## 21. Final MVP Definition

Omni MVP is successful when:

1. A user can visit an Amazon or Best Buy electronics product page.
2. The Chrome extension detects product title and price.
3. The extension sends data to the FastAPI backend.
4. The backend stores the product and price observation.
5. The backend generates a price context summary.
6. The backend returns a Buy / Wait / Watch / Avoid recommendation.
7. The extension displays the recommendation with an explanation.
8. The user can track the product and set a target price.
9. The ML pipeline has EDA, feature generation, training, and evaluation scripts.
10. The backend includes tests for validation, product handling, recommendation logic, and API behavior.
