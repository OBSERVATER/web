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
