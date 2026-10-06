# trade

我个人关于交易的想法：技术指标、观点、复盘。

## 指标

每个指标一个文件夹，里面是代码和详细讲解。

- [第一性原理面板](./indicators/first-principles-panel/)：只看价格、成交量和相对板块表现，一张表看清趋势、力量、位置与风险（TradingView Pine v6）
- [位置与风险面板](./indicators/position-risk-panel/)：离均线多远、一年位置、量价配合、波动收缩、止损与风险收益比、未回补缺口（TradingView Pine v6）

## 自动化

- [观察池日报](./scanner/)：每个交易日北京时间 06:15 自动扫描 [`watchlist.txt`](./watchlist.txt)，用与上面两个指标相同的固定公式（无 AI）生成 [`scan.md`](./scan.md) 并发邮件

## 想法

- `ideas/`：交易观点与想法

---
仅为个人记录与分享，不构成投资建议。
