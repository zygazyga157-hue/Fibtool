# Atrium Ingest Pack — Workspace Markdown (LLM Intake)
Version: v1.1  
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
- slug: fibtool-ecosystem
- code: EXH-FIB
- version: v1.1
- updatedAt: 2026-01-24  

### Exhibit title & thesis
- title: Fibtool Ecosystem - Algo Trading, Web3 & Subscription Platform
- thesis (one sentence): A comprehensive financial ecosystem combining Gann/Fibonacci algo trading, a Web3 decentralized marketplace, and a fiat subscription service.

### Exhibit status (choose one)
- status: Client-ready

### Exhibit tags (5–10)
- tags:
  - Python
  - Algorithmic Trading
  - Web3
  - Solidity
  - Next.js
  - FastAPI
  - Square of Nine
  - Fibonacci

### Atrium meta line (auto or custom)
- metaLine (suggested format): EXH-FIB / v1.1 / Updated 2026-01-24

---

## 2) PLACARD (Museum Label)
Write like a museum placard: compact, confident, clear.

- what (1–2 sentences): A professional-grade ecosystem featuring an algorithmic trading platform (Fibtool), a decentralized signal marketplace (Web3), and a subscription delivery system.
- why (1–2 sentences): To automate complex market analysis while democratizing access to institutional-grade signals through both centralized (Email) and decentralized (Blockchain) channels.
- approach (2–5 bullets, full sentences not required):
  - **Core Algo**: Automated Price Confluence Zones using Gann's Square of Nine & Fibonacci.
  - **Web3 Market**: Decentralized governance and signal escrow on Arbitrum.
  - **Delivery**: Multi-channel distribution via Telegram, Email, and DApp.
  - **Access**: Viewers can request to test and join the program via WhatsApp.

---

## 3) ROADMAP (Optional but recommended)
List milestones for this exhibit. Keep them concrete.

- roadmap:
  - [x] Beta Launch (Oct 2025)
  - [x] Core Analysis Engines (Fibonacci + Square of Nine Strategies)
  - [x] Multi-Timeframe Support Implementation
  - [x] Commercial Launch (Jan 2026)
  - [x] Full Automation Verification
  - [x] Candlestick Pattern Detection Integration
  - [x] Web3 Smart Contract Deployment (Testnet)
  - [x] Email Subscription System (MVP)

---

## 4) ARTIFACTS (Projects inside this Exhibit)

### Artifact 1: Fibtool Core & Candlesticks
#### Artifact ID
- id: fibtool-core-v1
- updatedAt: 2026-01-24

#### Artifact name
- name: Fibtool Core & Candlesticks

#### Artifact status (free text)
- status: Client-ready

#### Description (3–6 lines)
- description: |
  - Advanced algorithmic trading bot utilizing Gann's S9 and Fibonacci retracements.
  - Includes a lightweight Candlestick Pattern Detector (TA-Lib) for signal confirmation.
  - Features real-time Telegram reporting with HTML formatting and multi-indicator support.
  - Integrated risk management for MT5 automated trading.

#### Stack (5–12)
- stack:
  - Python 3.13+
  - MetaTrader 5 (MQL5)
  - Pandas & NumPy
  - TA-Lib
  - Telegram Bot API
  - Google Gemini AI

#### Proof & results
- results (0–6 bullets):
  - Analysis of 43 Fibonacci levels and 10+ S9 angles.
  - Real-time detection of Engulfing, Hammer, and Doji patterns.
  - Successful live trading integration with MT5.
  
#### Costs (if applicable)
- monthly: $50–$100
- oneTime: $8,500 (Valuation)

#### Funding (if applicable)
- needed: $5,000
- milestone: Scaling & Marketing
- breakdown (optional, must sum ~100%):
  - label: Infrastructure
    pct: 30%
  - label: Marketing
    pct: 40%
  - label: Dev
    pct: 30%

#### Work opportunities accepted
- acceptedTypes:
  - Contract
  - Research collab
- industries:
  - Fintech
  - Trading
- deliverables:
  - Automated signal setup
  - Custom strategy development
  - **Join via WhatsApp to test**

---

### Artifact 2: Fibtool Emailing System
#### Artifact ID
- id: fibtool-email-mvp
- updatedAt: 2026-01-24

#### Artifact name
- name: Fibtool Subscription Platform

#### Artifact status (free text)
- status: Shipped (MVP)

#### Description (3–6 lines)
- description: |
  - A subscription-based web platform to sell Fibtool plot outputs via email.
  - Full-stack solution with FastAPI backend and Next.js frontend.
  - Integrated PayNow (Zimbabwe) payment workflow.

#### Stack (5–12)
- stack:
  - FastAPI (Python)
  - Next.js (React)
  - PostgreSQL
  - Docker
  - PayNow

#### Costs (if applicable)
- monthly: $20
- oneTime: $2,500

---

### Artifact 3: Fibtool Web3 Marketplace
#### Artifact ID
- id: fibtool-web3-dao
- updatedAt: 2026-01-24

#### Artifact name
- name: Fibtool Decentralized Signals (Arbitrum)

#### Artifact status (free text)
- status: Research/Testnet

#### Description (3–6 lines)
- description: |
  - Suite of 11 smart contracts for a decentralized trading signal marketplace.
  - Features FIBT (ERC20) utility token and Strategy NFTs (ERC721).
  - Includes On-chain Governance, Staking, and MT5 Oracle verification.

#### Stack (5–12)
- stack:
  - Solidity
  - Hardhat
  - Arbitrum
  - Ethers.js
  - Node.js

#### Proof & results
- results (0–6 bullets):
  - 11 Smart Contracts implemented.
  - Trusted signal payments with escrow.
  - On-chain performance verification logic.

#### Costs (if applicable)
- monthly: $0 (Testnet)
- oneTime: $15,000 (Valuation)

---

## 5) REALTIME BIDDING / AUCTIONS (Optional)

### Auction: Acquirement (optional)
- auctionKind: `ACQUIREMENT`
- status: `LIVE`
- currency: `USD`
- openingBid: 5000
- minIncrement: 500
- endsAt: 2026-03-01T18:00:00Z
- antiSnipingSeconds: 60
- allowedBidTypes:
  - FIXED_PRICE
  - RETAINER
  - HOURLY_RATE

### Auction: Funding (optional)
- auctionKind: `FUNDING`
- status: `LIVE`
- currency: `USD`
- openingBid: 100
- minIncrement: 20
- allowedBidTypes:
  - SPONSOR_TIER
  - MILESTONE_SPONSOR

---

## 6) VISUALS (Optional, highly recommended)
Provide 1–4 visuals per artifact.

- images:
  - caption: No visuals currently configured
    href: 

---

## 7) PRIVACY / SAFETY NOTES (Optional)
- disclaimers:
  - “Educational purposes only; not financial advice.”
  - “Trading involves significant risk of loss.”
  - “Past performance is not indicative of future results.”

---

## 8) CHANGELOG (Optional)
- 2026-01-24 — Added Web3, Emailing System, and Candlesticks artifacts. Updated Roadmap.
- 2025-11-20 — Multi-Timeframe Support Implemented.
- 2025-10-15 — Beta Launch.

---
