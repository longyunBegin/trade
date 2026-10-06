# 观察池日报（自动扫描）

每个交易日自动扫描 [`watchlist.txt`](../watchlist.txt) 里的股票，把结果写进 [`scan.md`](../scan.md)，并发一封邮件。

**纯固定公式，没有任何 AI 参与。** 计算方法和本仓库两个 TradingView 指标完全相同，所以数字可以和图表上的面板对照：

- [第一性原理面板](../indicators/first-principles-panel/)：均线位置与排列、结构（突破/跌破前 20 根高低）、量比、ATR14、相对基准强弱、近低/近高
- [位置与风险面板](../indicators/position-risk-panel/)：离 MA20/MA50 多远（% 与 ATR 倍数）、一年位置、涨/跌量比、ATR 分位、止损/目标/风险收益比

此外还会对比前一天，列出 **今日变化**：新突破近高 / 新跌破近低、收盘上穿或下穿 MA20/50/200、均线排列变化、相对强弱由弱转强或由强转弱。

## 修改观察池

编辑仓库根目录的 `watchlist.txt`，一行一个 Yahoo Finance 代码，可选“逗号 + 基准代码”：

```
# 注释行以 # 开头
MU              # 不写基准，默认 SOXX
SIVE.ST, ^OMX   # 瑞典股票，用 OMX 斯德哥尔摩 30 指数做基准
```

代码写法以 Yahoo Finance 网站为准：美股直接写代码；瑞典加 `.ST`，港股如 `0700.HK`，A 股如 `600519.SS` / `000001.SZ`；指数前面带 `^`。

上市时间短的标的（比如 DRAM 只有约半年数据）照常计算：不够 200 根时 MA200 为空（和 Pine 一样按 na 处理，均线位置/排列会显示为“夹在均线间 / 均线纠缠”），一年位置按全部已有 K 线计算，并在表格下方备注“数据不足”。某只代码拿不到数据时，该行显示“数据缺失”，不影响其他标的。

## 运行时间

- 自动：**北京时间周二至周六 06:15**（GitHub cron `15 22 * * 1-5`，UTC）。美股收盘是北京时间 04:00（夏令时）或 05:00（冬令时），两种情况都在收盘之后。
- GitHub 的定时任务高峰期可能延迟几分钟到几十分钟，属正常现象。
- 美股假期当天没有新 K 线，`scan.md` 不变时不会产生提交（邮件仍会发，内容与上一交易日相同）。

## 手动运行

- 网页：仓库 **Actions** 标签 → 左侧选 **观察池日报** → 右侧 **Run workflow** → 选 `main` → **Run workflow**。
- 命令行：`gh workflow run scan.yml -R longyunBegin/trade`
- 本地：

  ```bash
  pip install -r scanner/requirements.txt
  python scanner/scan.py --no-email
  ```

  会生成 `scan.md` 和 `scanner/out/email.html`（邮件预览，不提交）。若在盘中运行，会自动丢弃当天未收盘的那根 K 线。

## 需要的 Secrets

在仓库 **Settings → Secrets and variables → Actions** 里设置（邮箱和密码不要写进代码，仓库是公开的）：

| 名称 | 内容 |
|---|---|
| `GMAIL_USER` | 发件 Gmail 地址 |
| `GMAIL_APP_PASSWORD` | Gmail **应用专用密码**（Google 账号开启两步验证后，在“安全性 → 应用专用密码”生成的 16 位密码，不是登录密码） |
| `MAIL_TO` | 收件地址，多个用英文逗号分隔 |

三个中缺任何一个，脚本会跳过发信，只更新 `scan.md`，运行仍然算成功。配置齐全但发信失败（如密码错误）时，运行会标红，方便发现问题。

## 数据来源

Yahoo Finance（通过 `yfinance`），免费，取日线收盘、约两年历史。价格为拆股调整、未做分红调整，和 TradingView 默认显示一致。免费数据偶尔会延迟或出错，若某天数字明显不对，以券商或 TradingView 为准。

想换成付费数据源（Polygon、Tiingo、券商 API 等），只需要改 `scanner/scan.py` 里的 `fetch_daily()` 函数，让它返回同样格式的日线表格（日期索引，Open/High/Low/Close/Volume 五列），其余计算和邮件都不用动。

---
不构成投资建议。
