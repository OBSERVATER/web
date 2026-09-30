# Public valuation source audit — 2026-09-30

This records **dated comparisons**, not synthetic backfill. The user's example values
are reference checkpoints, not a calibration target: values can differ by trading date,
calculation methodology and source update lag. Do not pick a source only because its
number is closest; verify series identity and weighting before using its history.

| Index / metric | User checkpoint (approx.) | Other public observation | Reported date | Methodology / qualification | Public URL |
|---|---:|---:|---|---|---|
| 中证红利 / DY | 4.26% | 4.25% | 2026-09-28 | ETF.run index TTM dividend yield; secondary current-value cross-check | https://www.etf.run/index/CSI/000922 |
| 中证红利 / DY | 4.26% | 4.27% | 2026-09-18 | Lixinger page summary, date differs; table adapter opportunistic only | https://www.lixinger.com/equity/index/detail/sh/000922/922/fundamental/valuation/dyr?metrics-type=mcw |
| 价值100 / PE | 8.89 | 10.09 | 2026-09-18 | Lixinger market-cap weighted; stale relative to checkpoint | https://www.lixinger.com/equity/index/detail/sz/980081/980081/fundamental/valuation/pe-ttm?metrics-type=mcw |
| 价值100 / PE | 8.89 | 11.52 | 2026-09-24 | ETF.run equal weight; **not interchangeable** with reconstructed weighted PE | https://www.etf.run/index/CNI/980081 |
| 医药50 / PB | 3.91 | 3.84 | 2026-09-18 | Lixinger market-cap weighted; not same date | https://www.lixinger.com/equity/index/detail/csi/931140/931140/fundamental/valuation/pb?metrics-type=mcw |
| 医药50 / PB | 3.91 | 3.29 | 2026-09-28 | ETF.run equal weight; **not interchangeable** with market-cap-weighted PB | https://www.etf.run/index/CSI/931140 |
| 恒生科技 / PS | 1.50 | 1.49 | 2026-09-29 | Baifenwei current PS, with ~317 weeks historical **percentiles** but not raw PS | https://baifenwei.com/index/hstech/ |

The historical adapter added in this change is optional and accepts **explicitly dated,
labelled HTML valuation table rows only**. A 403, missing table, summary-only page or
inconsistent metric produces no backfilled observations. There is no curve
interpolation, multiplier fitting, index-point-derived valuation or fabricated 10Y
history. Provider rows retain `source` and `weighting`; distinct weighting families
are not pooled into local 10Y statistics.

Lixinger's documented Open API requires a user token, so the monitor does not call
that endpoint. The public HTML adapter may still be blocked in GitHub Actions.
ETF.run summaries are for independent spot checks, not automatically treated as
10 years of dated history.

Next source-search priorities: authoritative older CSI dividend indicator archive,
weighted historical PE/PB for CNI 980081 and CSI 931140, and **raw** HSTECH PS
history (separate from percentile charts).

## GitHub Actions verification (2026-09-30)

Run 36678317190 completed successfully. Unit tests, image rendering, and artifact
publication passed. However, all three optional Lixinger public-HTML history GETs
returned HTTP 403 Forbidden from GitHub-hosted runners:

- 价值100 / PE: 403
- 中证红利 / DY: 403
- 医药50 / PB: 403

Therefore **zero verified historical raw-valuation weeks were added by these three
adapters** in this run. Do not treat successful workflow execution as successful
backfill. The existing canonical source was left intact. No token-backed private
API was attempted, and no weighting-incompatible ETF.run series was substituted.

## 2026-09-30: verified first-party guzhibiao historical API

The publicly served frontend JS at `https://guzhibiao.com/static/app.js`
requests `GET /api/index/{name}/history?indicator={indicator}`, and the
public data-transparency page identifies FundDB as its native valuation
provider. The endpoint was tested **inside GitHub Actions**, not only in a
browser.

| Target | API identity | Daily raw values | Weekly last-trading-day values | First week | Latest source value (2026-09-29) | Result |
|---|---|---:|---:|---|---:|---|
| 中证红利股息率 | 000922 / dividend | 2,438 | 514 | 2016-09-14 | 4.14% | Candidate history exported |
| 医药50 PB | 931140 / pb | 1,829 | 387 | 2019-03-22 | 3.94 | Candidate history exported |
| 价值100 PE | 980081 / pe | — | — | — | — | 404 on tested original name and three name variants |
| 恒生科技 PS | HSTECH / ps | — | — | — | — | 404, no raw PS available on this route |

The two successful series are persisted under
`data/candidates/guzhibiao_funddb_history.csv`, with source provenance,
index-code checks, date validation, and the explicit
`funddb-native-unverified` weighting marker. The primary
`data/history.csv` and `data/latest.json` remain unchanged.

**Same-date cross-check:** official CSI D/P2 for 中证红利 was 4.28% on
2026-09-29 while the third-party FundDB native DY was 4.14%; do not pool
them or use the FundDB historical percentiles for the official value.
Medical-50 primary reconstructed PB was ~3.885 on the same date versus
FundDB 3.94. The secondary chart is independently labelled and does not
compute or display a mixed-source 10-year percentile. Medical-50 also
started in 2019, so 387 weekly observations are not a full ten-year series.

Reproducible workflow: `Backfill public valuation candidates`.
The production image renderer can use those validated candidate rows as
a clearly labelled **historical visualization only** when the primary raw
history has fewer than 12 weekly points. Current large headline values
remain from the primary daily snapshot.
