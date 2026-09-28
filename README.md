# Cloud Valuation Monitor

一个完全在 GitHub Actions 云端运行的指数估值监控器：读取指数估值数据，Python 按 **10 年周频** 计算历史分位、20%/50%/80% 分位、均值、标准差与 Z-Score，并发送 HTML 邮件。

## 当前监控样例

- 价值100：PE-TTM
- 中证红利：股息率
- 恒生消费：PB-LF
- 医药50：PB-LF
- 恒生科技：PS-TTM
- 标普500：PE-TTM

编辑 `watchlist.yaml` 即可增删指数和指标。

## 统计口径

V1 使用理杏仁开放 API 提供的指数日度基础估值值，再由本项目自己完成历史统计。支持大陆、香港、美国指数，API 文档支持 PE-TTM / PB / PS-TTM / 股息率 / 收盘点位及时间范围数据。

历史统计按周采样：每个 ISO 周保留最后一个有数据的交易日，滚动窗口默认 10 年。

- 分位点：当前值在 10Y 周频样本中的升序历史位置
- 机会值：PE/PB/PS 取 20% 分位；股息率取 80% 分位
- 中位数：50% 分位
- 危险值：PE/PB/PS 取 80% 分位；股息率取 20% 分位
- Z-Score：`(当前值 - 10Y平均值) / 10Y总体标准差`

## GitHub Actions Secrets

数据源：
- `LIXINGER_TOKEN`

邮件：
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_SECURITY`：`starttls` 或 `ssl`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

## 调度

`.github/workflows/daily-monitor.yml` 默认北京时间工作日 07:35 运行，也可手动执行。

第一次成功运行会回填近 10 年历史数据到 `data/history.csv`，之后增量更新。最近一次结构化结果保存到 `data/latest.json`。

## 数据源验收

`Verify valuation sources` workflow 用于比较 2026-09-28 的参考快照：

- 价值100 PE-TTM：8.89
- 中证红利股息率：4.26
- 标普500 PE-TTM：25.45
- 恒生消费 PB-LF：2.29
- 医药50 PB-LF：3.91
- 恒生科技 PS-TTM：1.50

不同数据商的指数聚合口径可能不同，因此验收 workflow 只报告偏差，不会强行修正。

## 本地测试

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests -v
```

设计原则：数据源与统计计算分离；不把网页 DOM 作为唯一主源；数据不足时明确显示，不用旧值伪装成最新值。
