# Atrium Ingest Pack — Workspace Markdown (LLM Intake)
Version: v1.0  
Updated: 2026-01-24  

Use this file inside each **project workspace** so an LLM can extract consistent data to populate the **Atrium (Exhibits)** and **Exhibit pages (Artifacts/Projects)** in the Event Horizon Gallery portfolio.

> **How to use**
1) Copy this file into a workspace folder and fill it in.  
2) Keep the structure intact (headings + keys).  
3) The LLM should read this document and produce:
   - an **Atrium Exhibit Card** entry, and
   - one or more **Artifact** entries (projects), plus optional **Auction** configuration for bidding.

---

## 0) LLM OUTPUT REQUIREMENTS (Do Not Delete)
When parsing this file, the LLM must output **valid JSON** with this shape:

```json
{
  "exhibit": {
    "slug": "",
    "code": "",
    "version": "",
    "updatedAt": "",
    "title": "",
    "thesis": "",
    "status": "Shipped | In Progress | Research | Client-ready",
    "tags": [],
    "metaLine": "",
    "placard": { "what": "", "why": "", "approach": "" },
    "roadmap": { "items": [ { "label": "", "done": true } ] }
  },
  "artifacts": [
    {
      "id": "",
      "name": "",
      "status": "",
      "description": "",
      "stack": [],
      "proof": { "results": [], "links": [ { "label": "", "href": "" } ] },
      "costs": { "monthly": "", "oneTime": "" },
      "funding": {
        "needed": "",
        "milestone": "",
        "breakdown": [ { "label": "", "pct": "" } ]
      },
      "opportunities": {
        "acceptedTypes": [],
        "industries": [],
        "deliverables": []
      },
      "auctions": [
        {
          "auctionKind": "ACQUIREMENT | FUNDING",
          "status": "LIVE | PAUSED | ENDED",
          "currency": "USD",
          "openingBid": "",
          "minIncrement": "",
          "endsAt": "",
          "antiSnipingSeconds": 60,
          "allowedBidTypes": []
        }
      ],
      "updatedAt": ""
    }
  ]
}
```

### Normalization rules
- Dates use ISO format: `YYYY-MM-DD` or ISO datetime for `endsAt`.
- Amounts are strings (e.g., `"$1,200"` or `"1200"`). Keep it consistent.
- `slug` is lowercase, hyphenated (no spaces).
- Tags are short (1–3 words), title case or lower case.
- Links must be full URLs when possible.

---

## 1) EXHIBIT (Atrium Card + Exhibit Page Header)
### Exhibit identity
- slug: `<required>`  
- code: `EXH-__` (optional but recommended)  
- version: `v1.0`  
- updatedAt: `YYYY-MM-DD`  

### Exhibit title & thesis
- title: `<required>`  
- thesis (one sentence): `<required>`  

### Exhibit status (choose one)
- status: `Shipped | In Progress | Research | Client-ready`

### Exhibit tags (5–10)
- tags:
  - -

### Atrium meta line (auto or custom)
- metaLine (suggested format): `EXH-__ / v__ / Updated YYYY-MM-DD`

---

## 2) PLACARD (Museum Label)
Write like a museum placard: compact, confident, clear.

- what (1–2 sentences):  
- why (1–2 sentences):  
- approach (2–5 bullets, full sentences not required):
  - 
  - 

---

## 3) ROADMAP (Optional but recommended)
List milestones for this exhibit. Keep them concrete.

- roadmap:
  - [ ] 
  - [ ] 
  - [x] 

---

## 4) ARTIFACTS (Projects inside this Exhibit)
Create **one block per artifact**. Duplicate this section for multiple artifacts.

### Artifact Template
#### Artifact ID
- id: `<stable-id>` (e.g., `algo-backtester-v1`)  
- updatedAt: `YYYY-MM-DD`

#### Artifact name
- name: `<required>`

#### Artifact status (free text)
Examples: Building, Maintaining, Shipped, Iterating, Researching

- status:  

#### Description (3–6 lines)
- description: |
  - 

#### Stack (5–12)
- stack:
  - 

#### Proof & results
- results (0–6 bullets):
  - 
- links:
  - label: Repo
    href: 
  - label: Demo
    href: 
  - label: Write-up
    href: 

#### Costs (if applicable)
- monthly: (e.g., `$45–$180`)
- oneTime: (e.g., `$300–$900`)

#### Funding (if applicable)
- needed: (e.g., `$1,200`)
- milestone: (what the funding unlocks)
- breakdown (optional, must sum ~100%):
  - label: Data + Infra
    pct: 40%
  - label: Research + Testing
    pct: 30%
  - label: Deployment + Monitoring
    pct: 30%

#### Work opportunities accepted (per artifact)
- acceptedTypes:
  - Internship
  - Contract
  - Freelance
  - Research collab
- industries:
  - 
- deliverables (fast deliverables you can offer):
  - 

---

## 5) REALTIME BIDDING / AUCTIONS (Optional)
If you want Monopoly-style bidding on this artifact, fill one or both auction configs below.

> NOTE: Highest bid + bid type is always displayed on the site (driven by `auction_state`).

### Auction: Acquirement (optional)
- auctionKind: `ACQUIREMENT`
- status: `LIVE | PAUSED | ENDED`
- currency: `USD`
- openingBid: (e.g., `500`)
- minIncrement: (e.g., `25`)
- endsAt: (ISO datetime, e.g., `2026-02-01T18:00:00Z`) or leave blank for no timer
- antiSnipingSeconds: 60
- allowedBidTypes:
  - FIXED_PRICE
  - HOURLY_RATE
  - RETAINER

### Auction: Funding (optional)
- auctionKind: `FUNDING`
- status: `LIVE | PAUSED | ENDED`
- currency: `USD`
- openingBid: (e.g., `50`)
- minIncrement: (e.g., `10`)
- endsAt: (ISO datetime) or blank
- antiSnipingSeconds: 60
- allowedBidTypes:
  - DONATION
  - SPONSOR_TIER
  - MILESTONE_SPONSOR

---

## 6) VISUALS (Optional, highly recommended)
Provide 1–4 visuals per artifact.

- images:
  - caption: 
    href: 
  - caption:
    href:

- video:
  - caption:
    href:

---

## 7) PRIVACY / SAFETY NOTES (Optional)
If any artifact needs disclaimers (especially trading/finance):
- disclaimers:
  - “Educational purposes only; not financial advice.”
  - “No guarantees of returns.”

---

## 8) CHANGELOG (Optional)
- 2026-01-24 — Created workspace ingest pack.
- YYYY-MM-DD — 

---

# 9) COMPLETED EXAMPLE (Reference)
## Exhibit identity
- slug: algo-trading
- code: EXH-03
- version: v1.0
- updatedAt: 2026-01-24
- title: Algorithmic Trading
- thesis (one sentence): Statistical systems with disciplined risk controls and reproducible research.
- status: In Progress
- tags:
  - Python
  - Backtesting
  - Risk
  - Execution
  - Statistics
- metaLine: EXH-03 / v1.0 / Updated 2026-01-24

## Placard
- what: Researching and building systematic strategies with realistic cost/slippage modeling.
- why: Converting noisy markets into measurable decision systems with controlled risk.
- approach:
  - Walk-forward validation to reduce overfitting.
  - Regime filters to adapt behavior.
  - Monitoring-first deployment with alerts.

## Roadmap
- [x] Data ingestion baseline
- [x] Basic backtest metrics
- [ ] Paper trading integration
- [ ] Live execution (small allocation)

## Artifact
- id: algo-backtester-v1
- updatedAt: 2026-01-24
- name: Vectorized Backtesting Engine
- status: Building
- description: |
  - Vectorized backtesting engine with transaction cost + slippage modeling.
  - Metrics: drawdown, Sharpe proxy, exposure, turnover.
  - Designed for rapid strategy iteration and reproducible experiments.
- stack:
  - Python
  - Pandas
  - NumPy
  - Plotly
  - PostgreSQL
- results:
  - Reduced strategy iteration time from hours to minutes (vectorized runs).
- links:
  - label: Repo
    href: https://github.com/yourname/backtester
- monthly: $30–$120
- oneTime: $0–$400
- needed: $1,200
- milestone: Paper → Live small allocation with monitoring
- breakdown:
  - label: Data + Infra
    pct: 40%
  - label: Research + Testing
    pct: 30%
  - label: Deployment + Monitoring
    pct: 30%
- acceptedTypes:
  - Contract
  - Internship
  - Research collab
- industries:
  - Fintech
  - Quant funds
  - Risk analytics
- deliverables:
  - Backtest framework setup in 1–2 weeks
  - Signal research report + validation

## Auctions
- Acquirement:
  - status: LIVE
  - openingBid: 500
  - minIncrement: 25
  - endsAt: 2026-02-01T18:00:00Z
  - allowedBidTypes: [FIXED_PRICE, HOURLY_RATE, RETAINER]
- Funding:
  - status: LIVE
  - openingBid: 50
  - minIncrement: 10
  - allowedBidTypes: [DONATION, SPONSOR_TIER, MILESTONE_SPONSOR]

---
End of template.
