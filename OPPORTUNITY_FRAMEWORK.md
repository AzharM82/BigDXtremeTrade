# BigDXtremeTrade - Opportunity Framework

## Mission
Be prepared for the 1-3 asymmetric risk/reward setups the market gifts every week.
Plan before the bell. Execute with discipline. Manage risk ruthlessly.

---

## The 5 Opportunity Categories

### 1. Earnings Reaction Reversal (ERR)
**Setup:** Stock beats on Sales + EPS but gaps DOWN (or misses but gaps UP).
The "wrong" initial reaction creates a high-probability reversal trade.

**Why it works:**
- Algos react to headlines; humans react to context
- Institutional positioning takes time to adjust
- The "wrong" gap gets bought/sold aggressively once real traders show up

**Data Signals (Pre-Market Scan):**
| Signal | Source | Threshold |
|--------|--------|-----------|
| EPS Surprise % | Polygon.io Financials | Beat by >5% |
| Revenue Surprise % | Polygon.io Financials | Beat by >3% |
| Pre-market Gap Direction | Polygon.io Snapshot | Gap opposite to beat/miss |
| Pre-market Volume | Polygon.io Aggregates | >2x avg pre-market vol |
| Options IV Crush | Polygon.io Options | IV30 dropping >20% |
| Implied Move vs Actual Gap | Polygon.io Options + Snapshot | Actual gap < expected move |

**Entry Framework:**
- Wait for first 5-15 min reversal candle
- Enter on break of reversal candle high/low
- Stop: below/above the gap extreme
- Target: fill the gap (T1), pre-earnings close (T2), expected move in reversal direction (T3)

**Risk/Reward:** Typically 3:1 to 10:1 on weekly options

---

### 2. Overextension Mean-Reversion (OMR)
**Setup:** Multi-day runner that is stretched >5-10x ATR from the 50MA.
When futures/pre-market signal exhaustion, the snap-back is violent.

**Why it works:**
- Mean reversion is the strongest force in markets
- Extended moves attract late buyers who become forced sellers
- Options premiums are inflated, selling or buying opposing side is favorable

**Data Signals (Daily Scan):**
| Signal | Source | Threshold |
|--------|--------|-----------|
| ATR Multiple from 50MA | Polygon.io + calculated | >5x ATR from 50MA |
| Consecutive Days in Direction | Polygon.io Aggregates | >5 consecutive days |
| Volume Trend | Polygon.io Aggregates | Declining volume on last 2 days |
| RSI | Calculated from Polygon.io | >80 or <20 |
| Distance from 52W High/Low | FinViz | Within 5% of extreme |
| Relative Volume | FinViz | Below average (exhaustion) |
| Futures Direction | Polygon.io (pre-market) | Opposing the trend |

**Entry Framework:**
- Confirm futures/pre-market reversal signal
- Enter on first 15-min candle that breaks against the trend
- Stop: above/below the extreme
- Target: 50MA (T1), 20MA (aggressive T1), prior consolidation zone (T2)

**Risk/Reward:** Typically 2:1 to 5:1 on weekly/monthly options

---

### 3. Event Day Volatility (FOMC/CPI/NFP)
**Setup:** Known macro event dates where IV is priced in.
Trade the post-event directional move after the market commits.

**Data Signals:**
| Signal | Source | Threshold |
|--------|--------|-----------|
| Event Calendar | Hardcoded + Polygon.io | Known dates |
| IV Rank | Polygon.io Options | >70th percentile |
| IV vs HV Ratio | Polygon.io Options | IV > 1.5x HV |
| SPY/QQQ Pre-event Range | Polygon.io Aggregates | Tight 2-day range |
| VIX Level | Polygon.io | >18 (elevated fear) |

**Entry Framework:**
- Pre-event: Consider straddles if IV is cheap relative to expected move
- Post-event: Wait 30 min after announcement, enter in direction of commitment
- Stop: opposite side of post-event range
- Target: measured move based on the range breakout

---

### 4. Sector Rotation / Sympathy Play
**Setup:** Sector leader gaps on news but peers haven't moved yet.
Or: fade the gap if the news is sector-specific not company-specific.

**Data Signals:**
| Signal | Source | Threshold |
|--------|--------|-----------|
| Sector RS Rating | FinViz | Top 3 sectors |
| Leader vs Peer Performance | Polygon.io | >3% divergence |
| Industry Group Flow | FinViz | Positive/negative group momentum |
| Correlation to Leader | Calculated | >0.7 correlation, lagging move |

---

### 5. Opening Range Breakout (ORB) on High ADR%
**Setup:** Stocks with high ADR% (>5%) that form a tight first 15-30 min range,
then break out with volume.

**Data Signals:**
| Signal | Source | Threshold |
|--------|--------|-----------|
| ADR% | FinViz / Calculated | >5% |
| Opening Range Size | Polygon.io Intraday | <50% of ADR |
| Breakout Volume | Polygon.io Intraday | >1.5x avg 5min vol |
| RS Rating | FinViz | >80 |
| Market Trend | SPY Polygon.io | Aligned with breakout direction |

---

## Weekly Preparation Workflow

### Sunday Night (30 min)
1. Run **Earnings Scanner** → identify upcoming ERR candidates
2. Run **Overextension Scanner** → flag OMR setups forming
3. Check **Economic Calendar** → note event days
4. Review **Sector Rotation** dashboard → identify leading/lagging groups
5. Set alerts for key levels

### Pre-Market (6:00 AM - 9:30 AM ET)
1. Check overnight futures for OMR confirmations
2. Review earnings results vs estimates for ERR setups
3. Check pre-market gaps and volume
4. Finalize trade plans with specific levels
5. Size positions based on defined risk

### Market Hours
1. Execute plans only — no improvising
2. ORB scans in first 30 minutes
3. Monitor open positions
4. Journal every trade immediately

### Post-Market (15 min)
1. Review executed trades
2. Update journal with notes
3. Run scanners for next day
4. Adjust watchlist

---

## Risk Management Rules

1. **Max risk per trade:** 1% of account
2. **Max daily loss:** 3% of account → stop trading
3. **Position sizing formula:** `shares = (account * 0.01) / (entry - stop)`
4. **Options sizing:** Never risk more than the defined $ amount on premium
5. **Scale out:** 1/3 at T1, 1/3 at T2, 1/3 runner with trailing stop
6. **No revenge trading:** If stopped out, wait 15 min minimum before next trade
7. **Weekly target:** 3-5% → when hit, reduce size by 50%

---

## Data Architecture

### Primary Data Sources
- **Polygon.io REST API** — Historical bars, financials, options chain, snapshots
- **Polygon.io WebSocket** — Real-time quotes, trades, options flow
- **FinViz Elite** — Screener exports, RS ratings, sector data, insider activity

### Calculated Metrics
- ATR (14-period) and ATR Multiple from MA
- RSI (14-period)
- ADR% (20-day)
- Consecutive directional days
- IV Rank / IV Percentile
- Expected Move (from options straddle pricing)
- Relative Volume (current vs 20-day avg)
- Distance from key MAs (10, 20, 50, 200)
