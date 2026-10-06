# Sivers Semiconductors（SIVE）第一性原理基本面拆解

> 写于 2026-10-07（北京时间）。股价 / 汇率口径：SIVE.ST 2026-10-06 收 **SEK 35.34**，USD/SEK ≈ **9.99**（Yahoo，[S18]）。
> 框架：价值 = 公司一生能交给股东的现金，再按风险折现。按「收入 → 利润率 → 现金 → 能赚多久 → 有多确定 → 反推现价」六步拆。
> 标注约定：**推算** = 我基于公开数字的计算 / 推断，不是公司口径；**未找到** = 公开来源里没查到。

## 摘要

- **价值来自哪里**：今天的收入主要来自 **Wireless 的 NRE（开发服务费）**（2025 年 NRE 占 57%，Wireless 占 69%）；但市值主要押注的是 **Photonics：InP CW DFB 激光 / SOA**，卖给可插拔光模块、NPO/CPO 和 LiDAR 客户。Photonics 过去 12 个月收入只有 **SEK 84.1m**（推算）[S1]。
- **关键数字**：2025 年净销售 **SEK 302.8m**（Q2 报告重述口径；年报口径 306.6m）；H1 2026 收入 **SEK 115.6m（−20%）**，毛利率 **−4.5%**，经营现金流 **−119.2m** [S1]。7 月完成 **SEK 700m** 定增，可转债转股、定期贷款还清后公司称**无有息负债** [S1][S7]。总股本 **356,740,332** 股 → 总市值约 **SEK 126 亿 ≈ USD 12.6 亿**（推算）[S9][S18]。
- **现价隐含什么（推算）**：按 12–15% 折现率、再摊薄 10%、2030 年 20–30 倍 P/E、20% 净利率估算，2030 年收入需要约 **USD 3.6–6.1 亿**，相当于 2025 年约 USD 3,000 万的 **12–20 倍**（年复合约 68–82%）。公司自己给的长期目标是年复合 **25–30%** [S4]。
- **最值得盯的问题**：2027 年产品收入能否真正拐头？具体看三个节点：**① Q4 2026 收入是否如公司所说出现拐点**（Q3 报告 11/26 先看前瞻）；**② LiDAR 客户量产订单，以及 Jabil 1.6T beta → H1 2027 量产订单**；**③ 毛利率能否从负值回到正值并持续改善**（长期目标 65%）。

---

## 1. 收入 = 量 × 价

**结构（2025 年，Q2 报告重述口径，SEK m）[S1]**

| 分部 | 2025 | 其中 NRE | 其中硬件/产品 | H1 2026 | 过去 12 个月（推算） |
|---|---|---|---|---|---|
| Wireless（mmWave 波束成形 IC、SATCOM、FWA、国防） | 208.5 | 174.1 | 33.8 | 81.9（−19%） | 189.9 |
| Photonics（InP 激光 / SOA，Glasgow 晶圆厂） | 94.3 | 0 | 94.3 | 33.7（−23%） | 84.1 |
| 合计 | 302.8 | 174.1 | 128.1 | 115.6（−20%） | 274.1 |

- **Wireless 仍在公司体内**，没有剥离：2026-09-24 刚任命 Wireless 新任 MD [S20]。Photonics 曾计划通过 byNordic SPAC 分拆，公司 2024-11 已公开搁置（据既有笔记，本文未重新核对原文）。
- **口径提醒**：2025 年收入有三套数——年报（2026-05-13 发布）306.6m [S5][S6]，Q2 报告再次重述为 302.8m（更正 NRE 收入确认和外币折算错误）[S1]。管理层在 Q4 电话会上称 2025 年「product revenue」为 SEK 85.7m [S4]，和重述表里「Hardware revenue」128.1m 对不上，**口径未对齐、原因未找到**。
- **Q2 2026**：收入 53.8m（−12%，剔除汇率影响为 −10%）；硬件收入 +13%（剔除汇率影响为 +18%）；NRE 从 35.5m 降到 24.6m [S1][S2]。公司解释的原因：主动把资源从 NRE 挪到 2027 年的量产准备上，再加上美国国防预算延迟和汇率影响 [S1]。

**量（客户 / 设计导入 / 产能）**
- Photonics 数据中心：
  - **Jabil 1.6T 可插拔模块**：alpha 已完成，**Q4 2026 做 beta**，之后是客户认证，预计 **H1 2027 拿到量产订单**、**H2 2027 爬坡**。
  - 另有 **3 家**模组厂在评估 alpha 样品、**3 家**在做技术 / 供应评估，产品是 70/100 mW CW 激光 [S3]。
  - **NPO** 方向在送样 200 mW 单颗和 100 mW 阵列；**CPO** 需求在 200–400 mW，需求很分散，公司称「持续跟踪架构演进」[S3]。
  - **GlobalFoundries**：激光阵列进入 GF 硅光参考设计和 SCALE 平台（合作，不是订单）[S15]。
- **SemiNex**：项目初始金额约 **USD 3.4m**，送样和早期量产目标 **2H 2027** [S13]。
- **LiDAR 战略客户**（未具名）：Q4 2026 开始爬坡；公司称 2026–2030 年**非约束性**收入潜力为 **USD 23m（基准）– 58m（上行）**，更长的车型周期内为 USD 53–138m [S4]；Q2 时称订单「imminent」[S1]。
- Wireless：
  - **ALL.SPACE USD 8.2m** 2027 年量产订单 [S14]。
  - **Tachyon** 首批量产订单 USD 3m [S1]。
  - Tier-1 电信 FWA 产品预计 2026 年底发布 [S1]。
  - 美国 CHIPS Act EW Star 第二年合同约 **USD 6.6m**（年报口径）[S5]。
- **机会管道（pipeline）**：2026-07 为 **USD 1.2B**，较 2025 年底 +268% [S1]。注意它的定义：是 **2026–2030 五年累计**的非约束性收入潜力 [S1][S3]，不是年收入，也不是在手订单。即使 100% 转化，平均每年也只有约 USD 2.4 亿（推算）。
- **产能**：
  - Glasgow 扩产投资 **USD 30m**，目标 **>1 亿颗 CW DFB/年**，**2027 Q4** 投产 [S12]。
  - 新增了一家「立即可用、产能很大」的代工伙伴（未具名）[S1][S3]。
  - 长期模式是自有:代工 = **1:2** [S1]。按这个比例，总产能可能约为 Glasgow 的 3 倍（**推算**，公司没有给总量）。

**价（ASP）**
- 公司**未披露**激光 ASP（**未找到**）。CEO 的原话是「Pluggables remain very constrained on CW laser supply」[S1]、「Laser demand outstrips supply next 3 to 5 years」[S3]。这只是对供需的定性判断，没有价格数字。
- 社区里流传的「$50–100 / 8 通道阵列」「渠道涨价」等说法来自 X 作者，**不是 IR 口径**，不作为依据。

**客户集中度**：2025 年 **3 家客户 = SEK 183.4m，约占 60%**（年报 306.6m 口径；A 79.4 / B 55.2 / C 48.7），**三家都在 Wireless**，身份未披露 [S5]。也就是说，市场押注的 Photonics 目前还没有大客户贡献。

## 2. 利润率

| SEK m | 2025（重述） | H1 2026 | Q2 2026 |
|---|---|---|---|
| 毛利 | 17.5（**5.8%**） | −5.2（**−4.5%**） | −19.7（**−36.6%**） |
| R&D | −55.0 | −37.1 | −25.0 |
| 销售、管理及其他 | −154.0 | −116.8 | −73.2 |
| 调整后 EBITDA | −53.3 | −49.3 | −35.5 |
| EBIT | −181.9 | −158.4 | −116.9 |

来源：[S1]（毛利率为推算）

- Q2 的 EBIT 里有 **62.7m 一次性费用**：期权相关 50.3m，其中 42.9m 是股价从 10.71 涨到 63.15 带来的**社保费重估**（非现金）；美国双重上市准备 12.4m [S1][S11]。
- 毛利率为负的具体原因：报告没有按职能拆分期权和社保费，所以「剔除后的毛利率」**未找到**。推断原因包括：产量低，Glasgow 晶圆厂的固定成本摊不开；NRE 收入下降；COGS 里含收购 MixComm 形成的无形资产摊销（2025 年重述时曾把部分摊销移出 COGS [S1]）。
- **经营杠杆（推断）**：晶圆厂加研发团队（130 人，31 人是 PhD [S1]）以固定成本为主，所以收入翻倍对利润的拉动会远大于成本增加；反过来，产量不起来，毛利率会一直被固定成本压着。
- **公司给的路径（Q4 2025 电话会，2026-02-26）[S4]**：
  - 年收入约 **USD 50–55m**、其中产品占 **65%** 时实现**现金流盈亏平衡**，目标「约 2 年」。
  - 长期：收入年复合 **25–30%**，毛利率 **~65%**，R&D **~20%**，EBITDA 率 **~30%**。
  - Q2 时 CEO 改口为「从 **2028 年起**执行长期财务模型」[S1]。
  - 对照：过去 12 个月收入 SEK 274.1m ≈ USD 2,700 万（推算），离盈亏平衡还差约 **2 倍**。

## 3. 利润 → 现金

- **烧钱**：
  - 2025 年经营现金流 −38.5m，投资现金流 −54.6m [S1]。
  - H1 2026：经营现金流 **−119.2m**（Q2 −70.0m），投资 −18.2m，其中资本化开发支出 18.4m [S1]。
  - 过去 12 个月：经营现金流约 −120m（推算）。
- **现金**：6/30 为 **SEK 62.7m** [S1]。之后发生了：
  - +700m 定增（毛额，**每股 57 SEK**，较 6/30 收盘折价 9.7%）[S7]；
  - +7.5m 认股权证行权 [S9]；
  - −USD 5m 定期贷款偿还 [S1]。
  - **备考 ≈ SEK 7.2 亿**（推算：未扣发行费用、Q3 经营烧钱和 Glasgow 支出；实数要等 11/26 的 Q3 报告）。
- **资本开支**：Glasgow USD 30m ≈ SEK 3 亿（推算，按 ~10 SEK/USD），分布在 2026 H2–2027 Q4 [S12]。
- **跑道（推算）**：(7.2 亿 − 3 亿 capex) ÷ 每季 0.5–0.7 亿经营烧钱 ≈ **6–8 个季度**，前提是收入不改善，大致撑到 2028 年。正好和公司「约 2 年实现现金流盈亏平衡」的目标衔接，**缓冲不大**。CFO 原话：「we no longer need to focus on funding our transformation」[S3]。
- **年报的持续经营提示**：审计师（Deloitte）在 2025 年报中提示「**持续经营存在重大不确定性**」（没有因此出具保留意见）[S5]。这是融资之前的状态。
- **融资 / 摊薄史**：
  - 股本：2025-06-30 为 285,657,897 → 2025-12-31 为 311,333,572 → 2026-08-31 为 **356,740,332**，一年多 **+24.9%**（推算）[S1][S9]。
  - 2026 年内的几笔：
    - 4 月：定增 8,620,000 股，约 125m（约 14.5 SEK/股，推算）；
    - 7 月：定增 12,280,701 股，700m；
    - 7 月：USD 12m 可转债按 **4.77 SEK/股**转成 22,847,044 股；
    - 8 月：认股权证按 **4.53 SEK/股**行权 1,659,015 股。
    - 来源 [S1][S7][S8][S9][S10]。
  - 公司自持库存股 12,872,916 股，用于期权和社保费对冲 [S16]。
- **10/22 临时股东大会（EGM）是做什么的** [S16]：
  - ① 提前终止 Deloitte，改聘 **Ernst & Young**。理由是 Deloitte 已任 10 年（EU 537/2014 轮换要求），并为预计 **H1 2027 完成的美国双重上市**做准备；公告明确称**并非会计分歧**。
  - ② **P11 期权**：最多 **7,280,000** 份（约 **2.0%** 摊薄），加上现有 15,929,025 份期权，合计摊薄 **≤约 6.1%**。行权价 = 授予前 5 日 VWAP × **110%**，3 年后才能行权，**没有业绩条件**；计划在 Q3 报告（11/26）后首次授予。
  - ③④ 授权发行 / 回购 C 股，用于交付期权和支付社保费。
  - 股权登记日 **10/14**，参会 / 邮寄投票通知截止 **10/16**。
- **锁定期**：7 月定增后公司承诺 120 天内不再发新股 [S7]，按完成日推算约在 2026 年 11 月前后到期。

## 4. 能赚多久（护城河 / 周期 / 卡位）

- **能力**：
  - 自有 Glasgow InP 晶圆厂，CEO 称有 25 年以上 CW DFB / SOA 设计制造经验 [S3]；
  - 产品覆盖 70/100/200 mW 单颗和 100 mW 阵列（NPO 方向的产品还在送样）[S3]；
  - SOA 打开了光路交换机（OCS）方向，公司称新增约 **USD 40 亿可服务市场（SAM）**，但 CEO 自己说「early days」[S3]。
- **卡位**：Sivers 是做光源的商用供应商（merchant），把激光 / 光源卖给模组厂和 CPO 平台（Jabil、GF、SemiNex），**不和客户做同样的产品**。这是它和垂直整合厂商的区别：可以同时卖给多家模组厂，但也意味着议价能力取决于短缺能持续多久。
- **周期**：
  - 现在是**供给侧短缺**：公司在 Q2 电话会上引用 Lumentum CEO 的说法，「InP 短缺可能比内存更严重」[S3]。
  - 但 Glasgow 要 **2027 Q4** 才投产 [S12]。同期同行也在扩产（Lumentum、Coherent、WIN 等，以及 SMART×GF 开放代工，据既有笔记）。到 2028 年，短缺可能转为平衡，届时价格和份额要靠成本、可靠性认证和客户绑定来守。
- **技术路线风险**：III-V-on-Si 等单片 / 异质集成路线（如 Scintil）可能压缩分立外置激光的市场；CPO 激光规格因架构而异，**还没有定型** [S3]。
- **管理层变动**：Photonics CTO、CST Global 联合创始人 Andrew McKee 将退休，过渡到 2026 年底；新的 Photonics 工程 VP 来自 Amkor [S20]。

## 5. 有多确定（风险清单）

1. **时间表滑点**：Q1 时管理层称「remain on track to our full-year revenue growth plan」[S17]，结果 H1 收入同比 −20% [S1]。LiDAR 订单在 Q4 2025 电话会时说 Q4 2026 开始爬坡，Q2 时说「imminent」，**至今未见 PR**（截至 2026-10-07 MFN 最新 PR 仍是 9/29 的 EGM 通知 [S19]）。
2. **客户集中**：约 60% 收入来自 3 家 Wireless 客户 [S5]；Photonics 的量产客户还没有形成公开订单规模。
3. **毛利率**：目前为负 [S1]。长期 65% 的目标 [S4] 依赖产品占比和产能利用率，**目前没有任何一个季度验证过**。
4. **摊薄**：一年多股本 +25% [S1][S9]；期权潜在摊薄 ≤6.1% [S16]；跑道约 6–8 个季度（推算）。如果拐点推迟，可能还要融资。
5. **财报质量 / 治理**：2025 年数字两次重述（PCAOB 审计升级）[S1][S6]；2025 年报审计意见带持续经营重大不确定性提示 [S5]；EGM 换审计师（官方理由是 EU 轮换 + 美国上市准备）[S16]。
6. **政策 / 宏观**：美国国防预算延迟已经影响了 Wireless 收入 [S1][S11]；以 USD 计价销售、SEK 报表，汇率波动大 [S5]；美国对中国光模块的采购限制（S.5548 草案，属政策背景，据既有笔记）可能有双向影响。
7. **股价波动本身**：2025-10-06 收 3.67 → 2026-06-03 盘中高 110 → 2026-09-02 低 22.10 → 10-06 收 35.34 [S18]。价格大幅偏离基本面的时间可以很长。

## 6. 反推：现价隐含什么（推算，非预测）

**现价快照（推算）**
- 市值：356,740,332 股 × 35.34 = **SEK 12,607m ≈ USD 1.26B**；扣除库存股后 SEK 12,152m；含全部期权和 P11 的完全摊薄口径为 SEK 13,427m [S9][S16][S18]。
- 企业价值（EV）≈ 市值 − 备考净现金约 0.7B ≈ **SEK 119 亿**左右。
- 市值 / 过去 12 个月收入（274.1m）≈ **46 倍**；市值 / 过去 12 个月 Photonics 收入（84.1m）≈ **150 倍**。

**简单反推**。假设：
- 投资者要求的年回报 r = 12% 或 15%；
- 以 4 年后（≈2030 年末）作为估值时点；
- 期间再摊薄 10%；
- 届时进入稳态，净利率 20%（参照公司长期 EBITDA 率 ~30% [S4]，再扣折旧摊销和税，属假设）。

| r | 2030 年需要的市值 | 若 P/E 20× → 所需收入 | 若 P/E 30× → 所需收入 | 若 P/S 8× → 所需收入 |
|---|---|---|---|---|
| 12% | SEK 218 亿 | **≈ USD 5.5 亿** | ≈ USD 3.6 亿 | ≈ USD 2.7 亿 |
| 15% | SEK 243 亿 | **≈ USD 6.1 亿** | ≈ USD 4.0 亿 | ≈ USD 3.0 亿 |

**怎么读**
- 2025 年收入约 **USD 3,000 万**（按现汇率换算）。按 P/E 口径，到 2030 年需要做到 **12–20 倍**，年复合约 **68–82%**。公司自己的长期目标是年复合 25–30%，按这个速度 2030 年只有约 USD 0.9–1.1 亿 [S4]。
- 按 P/S 8× 的宽松口径，也需要约 USD 2.7–3.0 亿，相当于 **USD 1.2B 管道（2026–2030 五年累计）在 2030 这一年就要兑现约 1/4**，而且管道本身还得继续扩大。
- **容量交叉验证**：如果 2030 年需要 USD 4–6 亿收入，其中 70% 来自激光，那么 Glasgow 1 亿颗/年满产时，单颗 ASP 需要约 **USD 2.8–4.2**；如果再算上代工伙伴的产能，所需 ASP 会更低，或者说对产能利用率的要求更低。ASP 公司**未披露**，这一环**无法验证**。
- **结论（框架层面）**：现价已经计入了「Photonics 在 2027–2030 年实现多年高速放量，并且毛利率接近长期目标」的情景。估值主要取决于 **Photonics 能拿到多少产品订单、多快爬坡、毛利率能到多少**，而不是今天的收入。

**要盯的 2–3 件事**
1. **Q3 报告（2026-11-26）**：Q4 收入拐点的前瞻、毛利率能否转正、季末现金（验证跑道），以及 Glasgow capex 的进度。
2. **订单 PR**：LiDAR 量产订单；Jabil beta → H1 2027 量产订单；6 家模组厂里有谁转成具名订单。
3. **10/22 EGM 结果，以及之后的融资 / 上市动作**：P11 是否通过，美国双重上市进度（公司预期 H1 2027），锁定期到期（约 11 月）后有没有新的股本动作。

---

## 来源

- [S1] Sivers Interim Report Q2 2026（2026-08-27）：https://www.sivers-semiconductors.com/wp-content/uploads/2026/08/Sivers-Interim-report-Q226.pdf （镜像 https://mb.cision.com/Main/11695/4388331/4236264.pdf ）
- [S2] PR「Sivers Semiconductors Reports Q2 2026 Results…」（2026-08-27）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-reports-q2-2026-results-as-product-growth-record-pipeline-and-customer-ramps-position-company-for-growth-acceleration-6543505f
- [S3] Q2 2026 电话会文字稿（2026-08-27，第三方 earningscalls.dev，仅公开前半部分）：https://earningscalls.dev/transcripts/sivers-semiconductors-ab-publ_sive_earnings_call_transcript_2026-08-27
- [S4] Q4 2025 电话会文字稿（2026-02-26，earningscalls.dev）：https://earningscalls.dev/transcripts/sivers-semiconductors-ab-publ_sive_earnings_call_transcript_2026-02-26
- [S5] Annual Report 2025（2026-05-13 发布）：https://www.sivers-semiconductors.com/wp-content/uploads/2026/05/Sivers_annualreport_2025_final.pdf
- [S6] PR「publishes the 2025 Annual Report, adjusting prior reported financials…」（2026-05-13）：https://www.sivers-semiconductors.com/press/sivers-semiconductors-publishes-the-2025-annual-report-adjusting-prior-reported-financials-as-preparation-for-a-potential-dual-listing-in-the-united-states/
- [S7] PR 定增 SEK 700m（2026-07-01）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-has-resolved-on-a-directed-share-issue-of-shares-amounting-to-approximately-sek-700-million-a4130eba
- [S8] PR Bootstrap 可转债转股（2026-07-03）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-lender-bootstrap-europe-exercises-conversion-right-under-existing-convertible-loan-314f3dcb
- [S9] PR Bootstrap 认股权证行权（2026-08-13）：https://mfn.se/cis/a/sivers-semiconductors/bootstrap-exercises-warrants-in-sivers-semiconductors-bb8a1506 ；股本变动（2026-08-31）：https://mfn.se/cis/a/sivers-semiconductors/change-in-the-total-number-of-shares-and-votes-in-sivers-semiconductors-ab-b249e12d
- [S10] 股本变动（2026-07-31）：https://mfn.se/cis/a/sivers-semiconductors/change-in-the-total-number-of-shares-and-votes-in-sivers-semiconductors-ab-39de956e
- [S11] PR 社保费重估（2026-08-13）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-strong-share-price-appreciation-drives-revaluation-of-social-tax-liability-in-q2-2026-ce62dbe9
- [S12] PR Glasgow USD 30m 扩产（2026-09-03）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-invests-usd-30-million-to-expand-european-photonics-manufacturing-for-ai-datacenters-6c7a8503
- [S13] PR SemiNex USD 3.4m（2026-08-13）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-announces-3-4m-program-with-seminex-for-next-generation-inp-light-sources-used-to-power-ai-data-centers-ce8d8eec
- [S14] PR ALL.SPACE USD 8.2m（2026-06-09）：https://mfn.se/cis/a/sivers-semiconductors/all-space-awards-8-2m-production-order-to-sivers-semiconductors-for-ka-band-beamforming-ics-c26f39e4
- [S15] PR GlobalFoundries 合作（2026-06-02）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-sivers-and-globalfoundries-advance-ai-data-center-optical-solutions-c7523cc4
- [S16] EGM 通知（2026-09-29）：https://mfn.se/cis/a/sivers-semiconductors/notice-to-attend-an-extraordinary-general-meeting-of-sivers-semiconductors-ab-535ec0a1
- [S17] PR Q1 2026 中报（2026-05-29）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-ab-publ-publishes-interim-report-q1-january-march-2026-a14cb894
- [S18] Yahoo Finance chart API：SIVE.ST、USDSEK=X（2026-10-07 抓取）
- [S19] MFN Sivers 新闻列表（2026-10-07 约 00:10 北京时间抓取）：https://mfn.se/all/a/sivers-semiconductors
- [S20] PR 高管变动（2026-09-24）：https://mfn.se/cis/a/sivers-semiconductors/sivers-semiconductors-makes-changes-to-senior-leadership-team-for-next-phase-of-commercial-growth-a24ee907

---
仅为个人记录与分享，不构成投资建议。
