# 📈 Earnings Report Analysis Example

This example demonstrates using RalphOS to autonomously research, collect, and analyze quarterly earnings reports for stock market analysis.

## 🎯 What This Does

Ralph will:
1. Research upcoming earnings dates for specified tickers
2. Collect historical earnings data
3. Scrape earnings call transcripts
4. Analyze revenue, EPS, and guidance trends
5. Generate investment insights report

## 🚀 Quick Start

```bash
# 1. Copy example files to ralph directory
cp examples/earnings_analysis/prd.json scripts/ralph/prd.json
cp examples/earnings_analysis/progress.txt scripts/ralph/progress.txt

# 2. Edit prd.json to add your target tickers
# Default: AAPL, MSFT, GOOGL, AMZN, NVDA

# 3. Run Ralph
./scripts/ralph/ralph.sh 25
```

## 📁 Output Structure

```
earnings_data/
├── AAPL/
│   ├── earnings_history.json    # Historical EPS, revenue
│   ├── transcripts/             # Earnings call transcripts
│   │   ├── 2024_Q4.txt
│   │   └── 2025_Q1.txt
│   └── analysis.md              # AI-generated analysis
├── MSFT/
│   └── ...
├── calendar.json                # Upcoming earnings dates
├── sector_comparison.json       # Cross-ticker analysis
└── investment_report.md         # Final insights report
```

## 📋 Tasks Breakdown

| ID | Task | Description |
|----|------|-------------|
| US-001 | Setup | Create directory structure for each ticker |
| US-002 | Calendar | Fetch upcoming earnings dates from financial APIs |
| US-003 | History | Collect historical earnings (EPS, revenue, guidance) |
| US-004 | Transcripts | Scrape/fetch earnings call transcripts |
| US-005 | Analysis | Analyze trends, surprises, guidance changes |
| US-006 | Comparison | Cross-ticker sector comparison |
| US-007 | Report | Generate investment insights report |

## 🔧 Configuration

### Adding Tickers

Edit `prd.json` and update the `tickers` array:

```json
{
  "projectName": "Q1 2026 Earnings Analysis",
  "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
  "quarters": ["2025_Q4", "2026_Q1"],
  "outputDir": "earnings_data"
}
```

### Data Sources

Ralph will use web search and publicly available sources:
- Yahoo Finance (earnings dates, historical data)
- Seeking Alpha (transcripts, analysis)
- SEC EDGAR (10-Q filings)
- Company investor relations pages

## 📊 Sample Output

### earnings_history.json

```json
{
  "ticker": "AAPL",
  "data": [
    {
      "quarter": "2025_Q1",
      "earnings_date": "2025-01-30",
      "eps_estimate": 2.35,
      "eps_actual": 2.42,
      "eps_surprise": 0.07,
      "eps_surprise_pct": 2.98,
      "revenue_estimate": 124500000000,
      "revenue_actual": 125200000000,
      "revenue_surprise_pct": 0.56,
      "guidance": "positive",
      "stock_reaction": "+3.2%"
    }
  ]
}
```

### analysis.md

```markdown
# AAPL Earnings Analysis

## Key Metrics
- **EPS Beat Rate**: 4/4 quarters (100%)
- **Average Surprise**: +2.5%
- **Revenue Trend**: Growing 8% YoY

## Highlights
- iPhone revenue exceeded expectations
- Services segment continues strong growth
- China market showing recovery

## Risks
- Supply chain concerns in Asia
- Regulatory pressure in EU

## Outlook
Management raised guidance for Q2, citing strong demand...
```

## 💡 Customization Ideas

1. **Add Technical Analysis**
   - Include price action around earnings
   - Calculate implied move vs actual move

2. **Sentiment Analysis**
   - Analyze transcript tone
   - Track management confidence

3. **Sector Rotation**
   - Compare across sectors
   - Identify leaders/laggards

4. **Alert System**
   - Flag earnings surprises
   - Highlight guidance changes

## ⚠️ Notes

- Respect rate limits when scraping
- Some sources may require API keys
- Transcripts may have delays after earnings
- Always verify data from multiple sources

## 📄 Files in This Example

- `prd.json` - Task definitions
- `progress.txt` - Starting context and patterns
- `prompt.md` - Custom agent instructions for earnings analysis

