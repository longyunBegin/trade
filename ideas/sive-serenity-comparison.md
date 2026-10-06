# SIVE：Serenity 的建模 vs 我们的第一性原理拆解

> 写于 2026-10-07（北京时间）。对照对象：X 用户 **Serenity（[@aleabitoreddit](https://x.com/aleabitoreddit)）** 2026-03-16 至 2026-10-02 的 SIVE 相关帖，以及 2026-05-19 的 Substack 长文；我们这边是 [sive-fundamentals.md](./sive-fundamentals.md)（下文 [S#] 指该文来源）。
> 帖子日期按北京时间。标注约定：**推算** = 我的计算；**未回原文核对** = 只见于笔记 / 二手转述，没有重新打开原帖；作者原话中的 "not guidance" 等保留语气照录。

## 一句话结论

- Serenity **有部分量化，但没有完整模型**：他算了「产能 × 良率 × ASP = 收入上限」和「市值 / 毛利」，本人标注为 "not guidance, just illustrative modeling"（[P10]）。没有利润表、现金流、摊薄和折现，也没有逐年收入预测。
- 双方的根本分歧不在价格，而在**量能不能卖出去、什么时候卖出去**。Serenity 假设"短缺下合格产能都会被吸收"（[P4][P7b]）；我们从在手订单和公司披露出发，认为这一点目前**还没有证据**。
- 值得注意的一点（推算）：把 Serenity 2028 年的产能情景（年收入 USD 3.41–5.12 亿）套进我们的估值框架（20% 净利率、20–30 倍 P/E、12–15% 折现、不计摊薄），折回今天约 **USD 10–24 亿**，现价市值约 USD 12.6 亿 [S18]。换句话说，**Serenity 的基础情景大致就是现价已经计入的情景**。他的更高估值主要来自更大的产能（3 亿颗）、下游并购和溢价倍数。

## 对照表

| 步骤 | Serenity 的观点 / 假设（出处） | 我们 | 判定 | 差异的主要原因 |
|---|---|---|---|---|
| 1 收入：量 | 用**产能**推收入：① 拿 Win Semi 10% 的晶圆产能（每年 35,000 片的数字来自 @StormDirac 的回复）×65% 良率 → 年阵列收入 **USD 3.41–5.12 亿**，"if this capacity scenario plays out in 2028"（[P4]）；中点约 **4.27 亿/年**（[P5]）；② Glasgow 每年约 1 亿颗 → **USD 6.25–12.5 亿/年**，本人称"示意，非指引"（[P10]）；③ 加上 2 家外部代工，合计"maybe 300M"颗，"H2 2028 约 3 亿颗 realistic"（[P12][P15]）。客户靠供应链映射：Ayar、GFS、POET、O-Net、Lightmatter、Celestial、AMD、Apple 等，其中很多他自己标为 likely / mapping（[P7][P18]） | 用**订单 / 设计导入**推收入：Jabil 预计 H1 2027 拿量产订单，另有 6 家模组厂在评估，LiDAR 订单尚未公告；过去 12 个月 Photonics 收入只有 SEK 84.1m [S1] | **不同** | Serenity 默认"产能 = 收入"（"assume it gets sold given shortages"，[P7b]）；我们只把公司公告的订单当收入依据 |
| 1 收入：价 | 「Sivers 历史价格 **USD 50–100 / 8 通道阵列**」（[P10]），出处未说明；7 月模型用 USD 50–75（[P4]）；CIOE 展位交流称 Sivers **已提价**，幅度未披露（[P13][P14]） | 公司**未披露** ASP；反推只需单颗激光 **USD 2.8–4.2**（推算） | **不同** | Serenity 的假设折合单颗 USD 6.25–12.5（推算），比我们反推所需高 1.5–4.5 倍。所以**价格不是瓶颈，量和利用率才是**。ASP 两边都无法用 IR 验证 |
| 1 收入：pipeline | 报道了 USD 1.2B（+268%），但明确说"Not really a good figure to go off for revenue projections"，只用它衡量客户质量（[P6][P7b]） | USD 1.2B 是 **2026–2030 五年累计**的非约束性潜力 [S1] | **相同**（都不当收入用） | Serenity 没有点明"五年累计、非约束性"这一定义，但他也没有把它算成收入 |
| 1 收入：Wireless / NRE | 认为 SATCOM/Wireless "would be better off divested"（[P9]），模型里只算激光 | Wireless 占 2025 年收入 69%；三家大客户约占 60%，**全部**来自 Wireless [S1][S5] | **Serenity 未涉及**（建模层面） | 他只给 Photonics 期权定价，忽略了今天收入的主体和它下滑的拖累 |
| 2 利润率 | 采用「管理层 **50–60%+** 毛利率目标」的上沿（[P4]）；引用 AAOI 所说 CPO 激光毛利 55–65%（[P11]）；认为提价会带来毛利率扩张（[P14]） | 公司长期目标毛利率 **~65%**（Q4 2025 电话会）[S4]；H1 2026 毛利率 **−4.5%**，Q2 为 −36.6% [S1] | **方向相同，起点不同** | Serenity 跳过了"从负毛利爬到目标"的过程；他说的 50–60% 来自哪里未找到，和公司 ~65% 的口径对不上 |
| 3 利润 → 现金 | 只看调整后 EBITDA −USD 3.72m，原话"what to look at given one-off charges"（[P6]）；把 SEK 700m 融资视为利好 / 量产信号（[P3][P9b]） | H1 经营现金流 −SEK 119.2m，跑道约 6–8 个季度，Glasgow capex 约 SEK 3 亿，年报有持续经营提示 [S1][S5][S12]（推算） | **Serenity 未涉及** | 他的模型停在毛利，不算烧钱、capex 和融资缺口 |
| 3 摊薄 | 3 月把"为扩产而稀释"列为风险（[P1]）；6 月称融资若由 long-only 机构认购且折价不大就"very bullish"（[P3]）。他的倍数用的是当时市值 | 一年多股本 **+24.9%**；期权潜在摊薄 ≤6.1%；反推时假设再摊薄 10% [S1][S9][S16] | **不同** | 他的 MC/GP 是静态倍数，不扣未来摊薄 |
| 4 能赚多久 | 短缺会持续：转述 LITE CEO「2027 年只能满足 30% 需求，2029–2030 年才平衡」（[P17]）；即使全行业扩产，"would likely still be a demand imbalance"（[P11]）；Glasgow 1 亿颗/年让 Sivers 进入全球 Tier 1，2:1 混合模式下份额可能达 "low double digits"（[P10b]）；激光厂可以通过下游并购扩大 TAM（[P11]） | 2027 Q4 Glasgow 投产时同行也在扩产，到 **2028** 年短缺**可能**转为平衡；单片集成路线可能压缩分立激光市场 [S12][S3] | **不同** | 他认为短缺期更长（引 LITE CEO，平衡在 2029–30）；我们更早假设平衡、给竞争和技术替代更大权重。双方都承认同行会扩产（[P10b]） |
| 5 有多确定 | 他认为 thesis 只在两种情况下失败：**代工产能分配出问题、认证失败**（[P8]）；最不满的是管理层沟通和纳斯达克上市进度（[P9][P9b]） | 时间表滑点、客户集中、负毛利、摊薄、两次重述、持续经营提示、换审计师 [S1][S5][S16] | **部分相同** | 都盯认证 / 订单节点；财报质量和治理风险，在已核对的帖子里未见他提及 |
| 6 反推现价 | 不做反推，直接给目标倍数（见下一行） | 现价要求 2030 年收入 USD 3.6–6.1 亿，年复合 68–82%（推算） | **方法不同** | 方法不同：静态产能情景 vs 折现后的所需收入 |
| 估值 / 目标价 | 3/16 在约 USD 1.4 亿市值做多，个人牛市情景 **USD 100 亿+**（[P1][P1b]）；5/1 称"今天合理估值约 **USD 30 亿**"，"明年 USD 100 亿 very possible"（[P2]）；7/16 按 2028 情景算 **3.6–5.4 倍 MC/毛利**（[P4]）；倾向给激光公司更高溢价（[P11]） | 不给目标价；只说明现价隐含了什么 | **不同** | 他用远期产能毛利 × 主观倍数，不折现、不扣摊薄，Wireless 也不另行估值 |

## 和公司披露对不上的地方

1. **收入增速的量级**：按 2025 年约 USD 3,000 万算，Serenity 的 2028 情景（USD 3.41–5.12 亿）意味着三年年复合约 **125–157%**（推算）。公司给的长期目标是年复合 **25–30%**，而且"从 2028 年起"才执行长期模型 [S4][S1]。
2. **LiDAR 的 USD 53–138m**：Serenity 3/16 写成"projected revenue coming in"（[P1]）。公司口径是：这是**整个车型周期**的潜力；2026–2030 年为 USD 23–58m；**均为非约束性** [S4]。他的写法比公司更强。
3. **ASP 与毛利率口径**：「历史 USD 50–100/阵列」和「管理层 50–60%+ 毛利率目标」在我们核对过的 IR 材料里**都没找到**。公司公开的是 ~65% 长期毛利率 [S4]，没有披露 ASP。
4. **盈亏平衡**：公司说年收入 **USD 50–55m**、产品占 65% 时现金流盈亏平衡 [S4]。Serenity 没有提到这个中间节点；过去 12 个月收入约 USD 2,700 万（推算）。
5. 小差异：6/30 帖写的是"约 SEK 600m"融资（[P3]），最终为 **SEK 700m、每股 57 SEK** [S7]（他在 9/1 的帖里提到了"57 SEK"，见 [P9b]）。

## 值得借鉴、补进我们分析的

- **供需尺子**：LITE CEO 的 70%/30% 说法和「2029–2030 平衡」（[P17]，Serenity 转述，**未回原视频核对**）；TrendForce 估计全球 CW/EML 年产能约 6.08 亿颗，AVGO+LITE+住友合计约 3.35 亿（[P10b]，二手转述）。按此推算，Glasgow 的 1 亿颗约相当于全球 16%（时间口径不一）。我们原先写的「2028 年可能平衡」应改为 **2028–2030 区间**。
- **渠道信息**：CIOE 展位交流（三手信息，非 IR）：已提价、70mW 最紧、**200mW 尚未量产**、刚开始建中国办公室、8 束同温阵列（[P13][P14]）。200mW 未量产这一条和 CPO 时间表直接相关。
- **代工侧**：转述 Digitimes 的报道：Win Semi 的 CW 产品 H2 2026 逐步出货，2027–2028 年贡献有意义收入，并在推进 6 寸 InP（[P16]）。可以作为验证 Win 一侧时间表的线索。
- **公开合作伙伴**：我们漏列了 POET、O-Net/Enablence（ELS）、Ayar Labs、Lightium（[P7][P18]）。需要逐一用公司 PR 核实后再补，并标注"合作 ≠ 订单"。
- **可证伪的 thesis 失效条件**：代工产能分配和认证失败（[P8]），应补进我们的风险清单，作为两条最直接的反证。
- **政策**：转述 MS 的看法：潜在 FCC 限制更可能从中国制 3.2T 开始，对激光定价是利好（[P16b]）。这是作者解读，不是规则原文。

## 未能核实

- X MCP 余额为 0（返回 402 credits depleted），**没能用 MCP 拉时间线或做搜索**。原帖正文改用公共镜像 api.fxtwitter.com 逐条读取（2026-10-07 抓取），没有覆盖 10/2 之后的新帖。
- 只见于 BotMemory 笔记、**未回原文核对**的数字：
  - 6/1「若为硅谷私募值 USD 40–60 亿」、GS「光学 TAM USD 1,410 亿 / CPO USD 810 亿」：镜像正文被截断；
  - 另一份笔记里的「今日合理约 USD 300 亿 / 一年内 USD 1,000 亿 / 天花板 USD 6,000–8,000 亿+ / 2028 Q4 收入 USD 5 亿+」：原帖 [P2] 写的是约 **USD 30 亿**，推断笔记有数量级笔误，**不采用**。
- Apple、Lightmatter、Celestial、AMD、Nokia 等客户关系：Serenity 自己标为 high confidence / likely 的映射（[P18]），**公司没有点名**。

## 来源（Serenity 原帖，北京时间）

- [P1] 2026-03-16 16:54 https://x.com/aleabitoreddit/status/2033466880661606646
- [P1b] 2026-03-16 21:28 https://x.com/aleabitoreddit/status/2033535833085718996
- [P2] 2026-05-01 04:13 https://x.com/aleabitoreddit/status/2049945161174823025
- [P3] 2026-07-01 01:21 https://x.com/aleabitoreddit/status/2072007692684837039
- [P4] 2026-07-16 22:54 https://x.com/aleabitoreddit/status/2077768896061563339 （引用 @StormDirac 2026-07-15 的回复）
- [P5] 2026-08-09 08:23 https://x.com/aleabitoreddit/status/2086247069900300393
- [P6] 2026-08-28 00:35 https://x.com/aleabitoreddit/status/2093014569279189295
- [P7] 2026-08-30 17:04 https://x.com/aleabitoreddit/status/2093988125144207710
- [P7b] 2026-08-28 21:20 https://x.com/aleabitoreddit/status/2093327851957461082
- [P8] 2026-08-30 17:14 https://x.com/aleabitoreddit/status/2093990659866923407
- [P9] 2026-09-01 18:24 https://x.com/aleabitoreddit/status/2094733112920154584
- [P9b] 2026-09-01 19:20 https://x.com/aleabitoreddit/status/2094747290342998403
- [P10] 2026-09-03 18:06 https://x.com/aleabitoreddit/status/2095453263613341938
- [P10b] 2026-09-04 00:15 https://x.com/aleabitoreddit/status/2095546138510459218
- [P11] 2026-09-07 17:16 https://x.com/aleabitoreddit/status/2096890295128625153
- [P12] 2026-09-08 14:23 https://x.com/aleabitoreddit/status/2097209065151816191
- [P13] 2026-09-09 13:52 https://x.com/aleabitoreddit/status/2097563877273989456 （引用 @awodias 展位交流）
- [P14] 2026-09-11 18:30 https://x.com/aleabitoreddit/status/2098358633960726788 （引用 @SUOHA_AI 展位交流）
- [P15] 2026-09-22 00:08 https://x.com/aleabitoreddit/status/2102067535915123156
- [P16] 2026-09-23 22:14 https://x.com/aleabitoreddit/status/2102763548715753927
- [P16b] 2026-10-02 01:21 https://x.com/aleabitoreddit/status/2105709782854435274
- [P17] 2026-10-02 16:50 https://x.com/aleabitoreddit/status/2105943565918703696
- [P18] 2026-05-19 Substack《Sivers: The Undiscovered CPO Laser Chokepoint + Customer Mapping》https://aleabitoreddit.substack.com/p/sivers-semi-sive-the-cpo-laser-supplier
- 公司数据见 [sive-fundamentals.md 的来源列表](./sive-fundamentals.md#来源)。

---
仅为个人记录与分享，不构成投资建议。
