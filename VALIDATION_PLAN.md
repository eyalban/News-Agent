# Validation Plan — Daily Security Briefing Agent

## Overview
This document describes how to validate the accuracy and reliability of the News Agent pipeline: RSS fetching → filtering → deduplication → content enrichment → AI analysis → formatting → email delivery.

---

## 1. Unit Tests (Automated — `pytest`)

### 1.1 Relevance Filter (`test_relevance_filter.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| High-priority match | Title: "IAF pilot safe after mission" | `is_relevant → True` |
| Actor + Event match | Title: "Iran launches missiles at Israel" | `is_relevant → True` |
| Actor only (no event) | Title: "Iran's economy grows 3%" | `is_relevant → False` |
| Event only (no actor) | Title: "Missile test in North Korea" | `is_relevant → False` |
| HTML in summary | Summary: `<b>Iran</b> strike <a>Israel</a>` | `is_relevant → True` (HTML stripped) |
| Irrelevant article | Title: "Tech stocks rise on Wall Street" | `is_relevant → False` |

### 1.2 Deduplicator (`test_deduplicator.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| Identical URLs | Two articles, same URL, different sources | Keep higher-priority source |
| Similar titles (>0.6 Jaccard) | "Iran fires missiles at Israel" vs "Iran fires rockets at Israel" | Deduplicated to one |
| Distinct titles (<0.6) | "Iran fires missiles" vs "Israel strikes back at Iran" | Both kept |
| Short generic vs long specific | "Iran warns Israel" vs "Iran warns Israel of nuclear retaliation" | Kept separate (Jaccard < 0.6) |
| URL tracking params stripped | Same URL with `?utm_source=twitter` vs without | Deduplicated |
| Source priority ordering | Same story from Reuters vs Times of Israel | ToI kept (higher priority) |

### 1.3 Content Fetcher (`test_content_fetcher.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| Blocked domain | URL: `https://twitter.com/...` | Skipped (`_is_fetchable_url → False`) |
| Google News URL | URL: `https://news.google.com/...` | Skipped |
| Valid URL | URL: `https://timesofisrael.com/article` | Fetched |
| Enriched flag | Successfully fetched article | `article["enriched"] == True` |
| Content truncation | Article with 5000 chars | Truncated to 3000 + "..." |
| Short content rejected | Article with < 100 chars extracted | Returns None |

### 1.4 Article Selection (`test_ai_analyzer.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| Enriched articles prioritized | 30 enriched + 100 headlines (max=80) | All 30 enriched included |
| Casualty headlines second | 10 enriched + 50 casualty + 100 other (max=80) | 10 enriched + 50 casualty + 20 other |
| Respects max_count | 100 enriched (max=80) | Only 80 returned |
| Casualty keyword detection | Title: "3 killed in Israel missile strike" | Classified as casualty_headline |
| Non-casualty headline | Title: "Iran threatens retaliation" | Classified as other |

### 1.5 Report Formatter (`test_formatter.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| Critical status | `status: "קריטי"` | Red banner, 🔴 emoji |
| Quiet status | `status: "שקט"` | Green banner, 🟢 emoji |
| No strikes | `total_launches: 0, strikes: []` | "לא דווחו תקיפות" message |
| Strikes with data | Strikes list with origin, weapon, result | Table rendered with all columns |
| Casualty details | `casualty_details` with entries | Detail table rendered |
| No casualties | `killed: 0, injured: 0` | "לא דווחו נפגעים" message |
| Pilot safe | `pilot_status` contains "לא דווח על פגיעה" | Green ✅ icon |
| Pilot at risk | `pilot_status` contains warning | Orange ⚠️ icon |
| RTL attributes | Any HTML output | All elements have `direction:rtl` |

### 1.6 AI Prompt Schema (`test_schema.py`)
| Test Case | Input | Expected |
|-----------|-------|----------|
| Schema completeness | REPORT_SCHEMA | All 17 required fields present |
| Schema types | Each field | Correct JSON types |
| Strict mode | Schema config | `"strict": True, "additionalProperties": False` |

---

## 2. Integration Tests (Automated — `pytest`)

### 2.1 Pipeline Smoke Test
- Run the full pipeline with `--force` flag locally
- Assert: no exceptions thrown
- Assert: email is sent (or mock email delivery)
- Assert: report_data is not None
- Assert: report_data contains all required schema fields

### 2.2 Quiet-Day Fallback
- Mock RSS feeds to return 0 articles
- Assert: `analyze_all([])` returns quiet-day report
- Assert: status is "שקט", all counts are 0

### 2.3 AI Fallback
- Mock OpenAI to raise an exception
- Assert: fallback report (raw headlines) is generated
- Assert: email still sent

### 2.4 Feed Failure Resilience
- Mock one RSS feed to fail, others succeed
- Assert: pipeline completes with remaining feeds
- Assert: failed feed is logged as warning

---

## 3. AI Accuracy Validation (Manual + Semi-Automated)

This is the most critical validation. The AI must correctly distinguish:

### 3.1 Confusion Matrix Tests
Run the AI with curated article sets and verify:

| Scenario | Input Articles | Expected Output |
|----------|---------------|-----------------|
| **Offensive vs Defensive** | "200 Israeli aircraft strike Iran" + "Iran fires 40 missiles at Israel" | `total_launches=40` (NOT 200) |
| **Interception counting** | "IDF intercepted 90 of 125 missiles" | `total_intercepted=90, total_launches=125` |
| **Vague interception** | "Most missiles were intercepted" + no specific number | `total_intercepted ≈ 80% of total_launches` |
| **Impact counting** | "Missile hit building in Tel Aviv" + "2 impacts in Haifa" | `total_impact=3` |
| **Casualty separation** | "28 killed in Iran strikes" (on Israel) + "50 killed in Israeli strikes on Iran" | `killed=28` (Israel-only) |
| **Cumulative updates** | Early: "1 killed, 20 wounded" + Later: "28 killed, 3000 wounded" | `killed=28, injured=3000` (use higher) |
| **Casualty details** | "Woman, 40, killed in Tel Aviv" + "3 lightly injured in Haifa" | Two casualty_details entries with correct data |
| **Pilot mentions** | "IAF pilots participated in strikes, all returned safely" | `pilot_status` mentions participation + no harm |
| **Air base targeting** | "Nevatim air base targeted, no damage reported" | `airbase_status` mentions targeting |
| **Multi-wave attack** | Multiple strike events across different times/regions | Multiple rows in strikes table |

### 3.2 Ground Truth Comparison Protocol
When validating against a real day:
1. Run the pipeline: `python -m src.main --force`
2. Capture the JSON output from AI (add `--json-output` flag or read logs)
3. Independently research the same 12h window using 3+ major sources
4. Compare every field:

```
FIELD               REPORT    GROUND TRUTH    VERDICT
status              קריטי      קריטי           ✅
total_launches      200       ~200            ✅
total_intercepted   90        ~90             ✅
total_impact        21        ???             ⚠️ (hard to verify)
killed              1         1-28            ⚠️ (depends on timing)
injured             20        20-3000+        ⚠️ (depends on timing)
pilot_status        safe      safe            ✅
airbase_status      no damage censored        ✅
```

### 3.3 Accuracy Scoring
For each field, assign:
- **✅ Correct**: Exact match or within 10% of ground truth
- **⚠️ Partial**: Direction correct but numbers off by >10%
- **❌ Wrong**: Contradicts ground truth (e.g., reports 0 when ground truth > 0)
- **🔄 N/A**: Cannot verify (military censorship, fog of war)

Target: **Zero ❌ errors**, at most 2 ⚠️ per report.

---

## 4. Email Delivery Validation

### 4.1 Rendering Test
- Send test email to multiple clients: Gmail, Outlook, Apple Mail
- Verify:
  - RTL text renders correctly
  - Tables are properly aligned
  - Hebrew characters display correctly
  - Colors and status banners are visible
  - Links are clickable
  - Email fits mobile screens (< 600px width)

### 4.2 Subject Line
- Format: `תדריך ביטחוני | DD/MM | מצב: STATUS`
- Verify Hebrew renders in subject line across email clients

### 4.3 Delivery Reliability
- Verify Resend API key is valid
- Verify sender domain is configured
- Check spam folder (Resend free tier may trigger spam filters)
- Verify email arrives within 2 minutes of pipeline completion

---

## 5. End-to-End Validation Checklist

Run this checklist after any significant code change:

- [ ] **Source coverage**: ≥ 4 RSS feeds return articles
- [ ] **Article volume**: ≥ 50 articles fetched total
- [ ] **Relevance filter**: 50-80% pass rate (not too broad, not too narrow)
- [ ] **Dedup effectiveness**: ≥ 30% reduction from raw to deduped
- [ ] **Content enrichment**: ≥ 10 articles get full text
- [ ] **AI completes**: No timeout, no retry exhaustion
- [ ] **Status correct**: Matches actual threat level
- [ ] **Launches**: Only counts INCOMING projectiles (not Israeli offensive)
- [ ] **Intercepted**: Non-zero when interceptions are reported in news
- [ ] **Impact**: ≤ total_launches, reflects confirmed hits only
- [ ] **Casualties**: Israel-only, matches reported numbers
- [ ] **Casualty details**: Includes available identity info (name, age, city)
- [ ] **Pilot status**: Accurately reflects IAF pilot news
- [ ] **Email delivered**: Arrives in inbox (not spam)
- [ ] **HTML renders**: RTL, tables, colors all correct

---

## 6. Regression Prevention

### 6.1 Known Failure Modes (Fixed)
| Bug | Root Cause | Fix | Test |
|-----|-----------|-----|------|
| Launch count = 200 (Israeli jets, not missiles) | AI confused offensive for incoming | Prompt: explicit confusion warnings | Confusion matrix test |
| Casualties = 0 despite reports | Casualty headlines not reaching AI | Three-tier article selection | Article selection test |
| Dedup "black hole" | min-based similarity absorbed distinct titles | Jaccard (union-based) similarity | Dedup unit test |
| HTML tags in keyword matching | `<b>Iran</b>` didn't match "iran" | Strip HTML before matching | Relevance filter test |
| total_impact = total_launches | AI defaulted impact to launch count | Prompt: explicit constraint rule | Schema validation test |
| total_intercepted = 0 always | Prompt said "without a number = 0" | Allow estimation from "most intercepted" | Interception count test |

### 6.2 CI/CD Integration
Add to GitHub Actions:
```yaml
- name: Run unit tests
  run: pytest tests/ -v --tb=short
```
This ensures no regression on every push.

---

## 7. How to Run Tests

```bash
# Unit tests
pytest tests/ -v

# Single module
pytest tests/test_relevance_filter.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Full pipeline test (requires API keys in .env)
python -m src.main --force
```
