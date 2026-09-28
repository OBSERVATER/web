# Cloud Valuation Monitor

完全运行在 GitHub Actions 云端的指数估值监控器。目标是：**不注册任何行情/估值服务账号，不需要 API Token，也不需要自己的电脑或服务器在线。**

系统每天从匿名公开数据源读取估值，Python 保存周频历史并计算最多 10 年的：

- 当前值
- 历史分位
- 20% / 50% / 80% 分位
- 平均值
- 最大值 / 最小值
- 标准差
- Z-Score

然后生成 HTML 日报并通过 SMTP 邮件发送。

## 当前监控样例

- 价值100：PE-TTM
- 中证红利：股息率
- 恒生消费：PB-LF
- 医药50：PB-LF
- 恒生科技：PS-TTM
- 标普500：PE-TTM

编辑 `watchlist.yaml` 即可增删。

## 数据源原则

当前只允许无需登录、无需 Token 的公开来源：

1. **指数公司官方公开数据优先**
   - 国证指数公开 indexList：价值100等国证指数的滚动 PE
   - 中证指数官方 indicator XLS：中证指数 PE / 股息率等
2. **匿名公开估值接口**
   - 蛋卷基金公开指数估值接口，用作 PE/PB/股息率补充与交叉验证
3. **公开网页**
   - 对没有结构化匿名接口的指标（例如部分港股指数 PS/PB）使用公开网页文本解析

每条结果都会保存 `source`，不会把不同口径的数据悄悄混在一起。

## 重要：不伪造“10年统计”

很多公开免费源只提供当前值或最近一段历史。系统不会拿几周或几年数据冒充“10Y”。

只有当某指标至少积累 `minimum_history_weeks`（默认 450）个周样本时，才会启用本地 10Y 分位、机会值、危险值、均值与 Z-Score。

如果历史不足：

- 仍显示可靠的当前值
- 如果公开源本身提供历史分位，会标成“源站分位”
- 本地 10Y 统计显示“历史不足”
- GitHub Actions 会持续自动积累历史

## 邮件配置

估值数据不需要任何账号。

只有“发送邮件”本身需要你的 SMTP 凭据。在仓库：

`Settings → Secrets and variables → Actions`

设置：

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_SECURITY`：`starttls` 或 `ssl`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `MAIL_FROM`
- `MAIL_TO`

这些值只放在 GitHub Secrets，不写进仓库。

## GitHub Actions

### Daily valuation monitor

北京时间工作日 **07:35** 自动：

1. 抓取最新公开数据
2. 保存周频历史
3. 计算有足够历史的 10Y 统计
4. 生成 HTML
5. 发送邮件
6. 将 `data/history.csv` 与 `data/latest.json` 自动提交回仓库

### Verify public valuation sources

人工触发后，将公开源实际值与当前参考快照比较：

- 价值100 PE-TTM：8.89
- 中证红利股息率：4.26
- 标普500 PE-TTM：25.45
- 恒生消费 PB-LF：2.29
- 医药50 PB-LF：3.91
- 恒生科技 PS-TTM：1.50

这里只报告偏差，不用补偿系数把结果“调成正确答案”。

## 历史统计口径

按 ISO 周保留最后一个有数据的交易日；滚动窗口最多 10 年。

对于 PE / PB / PS：

- 机会值 = 20% 分位
- 中位数 = 50% 分位
- 危险值 = 80% 分位

对于股息率方向相反：

- 机会值 = 80% 分位
- 中位数 = 50% 分位
- 危险值 = 20% 分位

Z-Score：

```
(current - mean_10y) / stddev_10y
```

## 本地测试

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests -v
```

项目原则：数据源与统计计算分离；官方源优先；不依赖账户型 API；数据不足时明确显示，不用旧值或短历史伪装成完整 10 年估值。
