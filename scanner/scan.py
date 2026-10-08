#!/usr/bin/env python3
"""观察池日报：纯固定公式扫描（与 indicators/ 下两个 Pine 指标同一套公式），不涉及任何 AI。

用法：
    python scanner/scan.py               # 扫描 + 写 scan.md + （若配置了环境变量）发邮件
    python scanner/scan.py --no-email    # 只写文件
    python scanner/scan.py --force       # 忽略“休市/无新数据/已发过”检查（也可用环境变量 FORCE=true）

上一个美股交易日休市、美股没有新日线、或 scan.md 已是同一数据日期时，跳过（不写文件、不发信），退出码 0。

发信需要环境变量：GMAIL_USER、GMAIL_APP_PASSWORD、MAIL_TO（多个收件人用逗号分隔）。
缺任何一个就跳过发信，只写文件。
"""
from __future__ import annotations

import argparse
import html
import math
import os
import smtplib
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "watchlist.txt"
SCAN_MD = ROOT / "scan.md"
OUT_DIR = ROOT / "scanner" / "out"
DEFAULT_BENCH = "SOXX"
BJ = ZoneInfo("Asia/Shanghai")

# ---- 参数（与 Pine 指标默认值一致）----
MA_FAST, MA_MID, MA_SLOW = 20, 50, 200
ATR_LEN = 14
LOOKBACK = 20        # 结构/近高低回看根数
LEN52 = 252          # 一年 K 线数
VOL_LEN = 20         # 量价统计天数
ATR_PCT_LEN = 120    # 波动比较区间
ATR_MULT = 2.0       # ATR 止损倍数

# 各交易所收盘时间（本地时间）。脚本若在盘中运行，会丢弃当天未走完的 K 线，避免用盘中价。
EXCHANGE_CLOSE = {
    "America/New_York": (16, 0),
    "America/Chicago": (15, 0),
    "Europe/Stockholm": (17, 30),
    "Europe/London": (16, 30),
    "Europe/Berlin": (17, 30),
    "Europe/Paris": (17, 30),
    "Europe/Amsterdam": (17, 30),
    "Asia/Shanghai": (15, 0),
    "Asia/Hong_Kong": (16, 10),
    "Asia/Tokyo": (15, 30),
    "Asia/Seoul": (15, 30),
    "Asia/Taipei": (13, 30),
}
CLOSE_BUFFER = timedelta(minutes=20)


# =====================================================================
# 数据获取 —— 换数据源只需要改这个函数，返回同样格式的 DataFrame 即可：
#   index = 日期（datetime.date 升序），列 = Open/High/Low/Close/Volume
# =====================================================================
def _patch_missing_close(tk, df: pd.DataFrame) -> pd.DataFrame:
    """Yahoo 偶尔给出“有成交量、收盘价却是空”的最新日线（常见于欧股，如 SIVE.ST）。
    这种情况用当天的 1 小时 K 线补齐开高低收，避免整天被丢掉、数据落后一天。"""
    if df.empty or not pd.isna(df["Close"].iloc[-1]):
        return df
    try:
        intra = tk.history(period="5d", interval="1h", auto_adjust=False, actions=False)
        if intra is None or intra.empty:
            return df
        day = df.index[-1].date()
        bars = intra[[ts.date() == day for ts in intra.index]].dropna(subset=["Close"])
        if bars.empty:
            return df
        df = df.copy()
        idx = df.index[-1]
        df.loc[idx, "Open"] = bars["Open"].iloc[0]
        df.loc[idx, "High"] = bars["High"].max()
        df.loc[idx, "Low"] = bars["Low"].min()
        df.loc[idx, "Close"] = bars["Close"].iloc[-1]
        if pd.isna(df.loc[idx, "Volume"]):
            df.loc[idx, "Volume"] = bars["Volume"].sum()
    except Exception:
        pass
    return df


def fetch_daily(symbol: str, period: str = "2y", retries: int = 3) -> pd.DataFrame:
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            tk = yf.Ticker(symbol)
            df = tk.history(period=period, interval="1d", auto_adjust=False, actions=False)
            if df is None or df.empty:
                raise ValueError("无数据")
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df = _patch_missing_close(tk, df)
            df = df.dropna(subset=["Close"])
            tz = str(df.index.tz) if df.index.tz is not None else None
            # 盘中运行时丢弃当天未收盘的 K 线（与“日线收盘”口径保持一致）
            if tz in EXCHANGE_CLOSE and len(df) > 0:
                now_local = datetime.now(ZoneInfo(tz))
                last_day = df.index[-1].date()
                h, m = EXCHANGE_CLOSE[tz]
                close_dt = datetime(last_day.year, last_day.month, last_day.day, h, m, tzinfo=ZoneInfo(tz))
                if last_day == now_local.date() and now_local < close_dt + CLOSE_BUFFER:
                    df = df.iloc[:-1]
            df.index = [ts.date() for ts in df.index]
            df = df[~pd.Index(df.index).duplicated(keep="last")]
            df["Volume"] = df["Volume"].fillna(0).astype(float)
            if df.empty:
                raise ValueError("无已收盘数据")
            try:
                meta = tk.get_history_metadata() or {}
                name = meta.get("shortName") or meta.get("longName") or ""
            except Exception:  # noqa: BLE001
                name = ""
            df.attrs["name"] = str(name)
            df.attrs["tz"] = tz or ""
            return df
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{symbol} 获取失败：{last_err}")


# =====================================================================
# Pine 等价函数
# =====================================================================
def pine_rma(src: pd.Series, length: int) -> pd.Series:
    """ta.rma：首值为前 length 个有效值的 SMA，之后 alpha = 1/length 递推。"""
    vals = src.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    alpha = 1.0 / length
    prev = np.nan
    valid = []
    for i, v in enumerate(vals):
        if math.isnan(prev):
            if not math.isnan(v):
                valid.append(v)
            if len(valid) == length:
                prev = sum(valid) / length
                out[i] = prev
        else:
            if not math.isnan(v):
                prev = alpha * v + (1 - alpha) * prev
            out[i] = prev
    return pd.Series(out, index=src.index)


def pine_atr(df: pd.DataFrame, length: int) -> pd.Series:
    """ta.atr：真实波幅（首根为 high-low）的 RMA。"""
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [df["High"] - df["Low"], (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()], axis=1
    ).max(axis=1)
    tr.iloc[0] = df["High"].iloc[0] - df["Low"].iloc[0]
    return pine_rma(tr, length)


def nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def gt(a, b) -> bool:  # Pine 中与 na 比较一律为 false
    return not nan(a) and not nan(b) and a > b


def lt(a, b) -> bool:
    return not nan(a) and not nan(b) and a < b


# =====================================================================
# 单只股票计算
# =====================================================================
@dataclass
class Result:
    symbol: str
    bench: str
    ok: bool = False
    error: str = ""
    date: str = ""
    bars: int = 0
    v: dict = field(default_factory=dict)
    changes: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    name: str = ""       # 名称（仅用于邮件展示）
    tz: str = ""         # 交易所时区，用于判断是否美股


def state_at(i: int, s: dict) -> dict:
    """取第 i 根 K 线上的各项读数（与 Pine 在该根上的输出一致）。"""
    g = lambda name: float(s[name].iloc[i]) if not pd.isna(s[name].iloc[i]) else float("nan")  # noqa: E731
    close, ma20, ma50, ma200 = g("close"), g("ma20"), g("ma50"), g("ma200")
    prev_hh, prev_ll = g("prev_hh"), g("prev_ll")
    above_all = gt(close, ma20) and gt(close, ma50) and gt(close, ma200)
    below_all = lt(close, ma20) and lt(close, ma50) and lt(close, ma200)
    pos_txt = "价在三线上方" if above_all else "价在三线下方" if below_all else "夹在均线间"
    align_txt = "多头排列" if gt(ma20, ma50) and gt(ma50, ma200) else "空头排列" if lt(ma20, ma50) and lt(ma50, ma200) else "均线纠缠"
    struct_txt = "突破近高" if gt(close, prev_hh) else "跌破近低" if lt(close, prev_ll) else "区间内"
    rs, rs_ma = g("rs"), g("rs_ma")
    rs_txt = "无数据" if nan(rs) or nan(rs_ma) else ("偏强" if rs > rs_ma else "偏弱")
    return dict(close=close, ma20=ma20, ma50=ma50, ma200=ma200, pos_txt=pos_txt, align_txt=align_txt,
                struct_txt=struct_txt, rs_txt=rs_txt)


MAX_GAPS = 10  # 与 Pine 的 maxGaps 默认值一致


def unfilled_gaps(df: pd.DataFrame, max_gaps: int = MAX_GAPS) -> list[tuple[int, float, float, object]]:
    """未回补跳空缺口（逐根移植自 position-risk-panel/panel.pine 第 6 部分）。

    每根 K 线：先检查旧缺口是否被回补（向上缺口 low <= 缺口下沿；向下缺口 high >= 缺口上沿）并移除，
    再记录新缺口（向上：low > 前高，上沿=low、下沿=前高；向下：high < 前低，上沿=前低、下沿=high），
    只保留最近 max_gaps 个（超出时丢掉最早的）。返回 [(方向, 上沿, 下沿, 产生日期), ...]，按产生顺序。
    """
    hi, lo = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    dates = list(df.index)
    gaps: list[tuple[int, float, float, object]] = []
    for i in range(len(df)):
        if gaps:
            gaps = [g for g in gaps if not (lo[i] <= g[2] if g[0] == 1 else hi[i] >= g[1])]
        if i == 0:
            continue
        if lo[i] > hi[i - 1]:
            gaps.append((1, lo[i], hi[i - 1], dates[i]))
        elif hi[i] < lo[i - 1]:
            gaps.append((-1, lo[i - 1], hi[i], dates[i]))
        if len(gaps) > max_gaps:
            gaps.pop(0)
    return gaps


def compute(symbol: str, df: pd.DataFrame, bench_close: pd.Series | None, bench: str) -> Result:
    r = Result(symbol=symbol, bench=bench)
    n = len(df)
    r.bars = n
    r.date = str(df.index[-1])
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]

    s = {
        "close": close,
        "ma20": close.rolling(MA_FAST).mean(),
        "ma50": close.rolling(MA_MID).mean(),
        "ma200": close.rolling(MA_SLOW).mean(),
        "prev_hh": high.shift(1).rolling(LOOKBACK).max(),
        "prev_ll": low.shift(1).rolling(LOOKBACK).min(),
    }
    if bench_close is not None and len(bench_close) > 0:
        b = bench_close.reindex(df.index.union(bench_close.index)).sort_index().ffill().reindex(df.index)
        rs = close / b
    else:
        rs = pd.Series(np.nan, index=df.index)
    s["rs"] = rs
    s["rs_ma"] = rs.rolling(20).mean()

    atr = pine_atr(df, ATR_LEN)
    hh = high.rolling(LOOKBACK).max()
    ll = low.rolling(LOOKBACK).min()
    vol_ma = vol.rolling(20).mean()
    up_vol = vol.where(close > close.shift(1), 0.0).rolling(VOL_LEN).sum()
    down_vol = vol.where(close < close.shift(1), 0.0).rolling(VOL_LEN).sum()

    i = n - 1
    cur = state_at(i, s)
    c = cur["close"]
    prev_close = float(close.iloc[i - 1]) if n >= 2 else float("nan")
    chg = (c / prev_close - 1) * 100 if not nan(prev_close) and prev_close else float("nan")
    a = float(atr.iloc[i]) if not pd.isna(atr.iloc[i]) else float("nan")
    hh_i = float(hh.iloc[i]) if not pd.isna(hh.iloc[i]) else float("nan")
    ll_i = float(ll.iloc[i]) if not pd.isna(ll.iloc[i]) else float("nan")
    vm = float(vol_ma.iloc[i]) if not pd.isna(vol_ma.iloc[i]) else float("nan")
    vol_ratio = float(vol.iloc[i]) / vm if not nan(vm) and vm > 0 else float("nan")

    def dist(ma):
        if nan(ma) or ma == 0:
            return float("nan"), float("nan")
        return (c - ma) / ma * 100, ((c - ma) / a if not nan(a) and a > 0 else float("nan"))

    d20p, d20a = dist(cur["ma20"])
    d50p, d50a = dist(cur["ma50"])

    # 一年位置：252 根或全部可用
    n52 = max(1, min(i + 1, LEN52))
    hi52 = float(high.iloc[i - n52 + 1:i + 1].max())
    lo52 = float(low.iloc[i - n52 + 1:i + 1].min())
    pos52 = (c - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else float("nan")

    # 量价
    uv = float(up_vol.iloc[i]) if not pd.isna(up_vol.iloc[i]) else float("nan")
    dv = float(down_vol.iloc[i]) if not pd.isna(down_vol.iloc[i]) else float("nan")
    ud = uv / dv if not nan(dv) and dv > 0 and not nan(uv) else float("nan")

    # ATR 分位（120 根或全部可用）
    n_atr = max(1, min(i + 1, ATR_PCT_LEN))
    win = atr.iloc[i - n_atr + 1:i + 1].dropna()
    if len(win) and not nan(a):
        ahi, alo = float(win.max()), float(win.min())
        atr_rank = (a - alo) / (ahi - alo) * 100 if ahi > alo else float("nan")
    else:
        atr_rank = float("nan")

    # 止损 / 目标 / 风险收益比
    stop_atr = c - ATR_MULT * a if not nan(a) else float("nan")
    stop = max(ll_i, stop_atr) if not nan(ll_i) and not nan(stop_atr) else float("nan")
    stop_src = "近低" if not nan(stop) and stop == ll_i else f"{ATR_MULT:g}ATR"
    risk = c - stop if not nan(stop) else float("nan")
    is_breakout = not nan(hh_i) and c >= hh_i
    target = (c + 2 * risk if is_breakout else hh_i) if not nan(risk) and not nan(hh_i) else float("nan")
    rr = (target - c) / risk if not nan(risk) and risk > 0 and not nan(target) else float("nan")

    r.v = dict(cur, chg=chg, vol_ratio=vol_ratio, atr=a, hh=hh_i, ll=ll_i, d20p=d20p, d20a=d20a, d50p=d50p,
               d50a=d50a, pos52=pos52, n52=n52, ud=ud, atr_rank=atr_rank, stop=stop, stop_src=stop_src,
               risk=risk, target=target, is_breakout=is_breakout, rr=rr)

    # 未回补缺口：最近的上方缺口（下沿 > 收盘中最小的下沿）、最近的下方缺口（上沿 < 收盘中最大的上沿）
    gaps = unfilled_gaps(df)
    above = [g[2] for g in gaps if g[2] > c]
    below = [g[1] for g in gaps if g[1] < c]
    r.v.update(gaps=gaps, gap_n=len(gaps), gap_above=min(above) if above else float("nan"),
               gap_below=max(below) if below else float("nan"))

    # 数据不足提示（Pine 中对应值为 na，均线位置/排列会落到“夹在均线间/均线纠缠”）
    if n < MA_SLOW:
        r.notes.append(f"仅 {n} 根K线，MA200 不足")
    if n < LEN52:
        r.notes.append(f"一年位置按全部 {n} 根计")

    # ---- 较前一日的变化 ----
    if n >= 2:
        prev = state_at(i - 1, s)
        if cur["struct_txt"] != prev["struct_txt"] and cur["struct_txt"] in ("突破近高", "跌破近低"):
            r.changes.append(("up" if cur["struct_txt"] == "突破近高" else "down", f"新{cur['struct_txt']}"))
        for key, label in (("ma20", "MA20"), ("ma50", "MA50"), ("ma200", "MA200")):
            pc, pm, cc, cm = prev["close"], prev[key], cur["close"], cur[key]
            if nan(pm) or nan(cm):
                continue
            if pc <= pm and cc > cm:
                r.changes.append(("up", f"上穿 {label}"))
            elif pc >= pm and cc < cm:
                r.changes.append(("down", f"下穿 {label}"))
        if cur["align_txt"] != prev["align_txt"]:
            kind = "up" if cur["align_txt"] == "多头排列" else "down" if cur["align_txt"] == "空头排列" else "flat"
            r.changes.append((kind, f"均线排列：{prev['align_txt']} → {cur['align_txt']}"))
        if prev["rs_txt"] != cur["rs_txt"] and "无数据" not in (prev["rs_txt"], cur["rs_txt"]):
            r.changes.append(("up" if cur["rs_txt"] == "偏强" else "down", f"相对 {bench} 转{cur['rs_txt'][-1]}"))
    r.ok = True
    return r


# =====================================================================
# 格式化
# =====================================================================
def fp(x, d=2) -> str:
    return "—" if nan(x) else f"{x:,.{d}f}"


def fpct(x, d=1) -> str:
    return "—" if nan(x) else f"{x:+.{d}f}%"


def dist_txt(p, a) -> str:
    if nan(p):
        return "—"
    if nan(a):
        return fpct(p)
    tag = "偏离大" if abs(a) >= 3 else "贴近" if abs(a) <= 1 else "正常"
    return f"{fpct(p)}（{a:+.1f}ATR {tag}）"


def pos52_txt(x) -> str:
    if nan(x):
        return "—"
    return f"{x:.0f}% " + ("高位" if x >= 80 else "低位" if x <= 20 else "中间")


def ud_txt(x) -> str:
    if nan(x):
        return "—"
    return f"{x:.2f} " + ("买盘主导" if x >= 1.2 else "卖盘主导" if x <= 0.8 else "均衡")


def atr_rank_txt(x) -> str:
    if nan(x):
        return "—"
    return f"{x:.0f}% " + ("收缩" if x <= 20 else "扩张" if x >= 80 else "正常")


def stop_txt(v) -> str:
    if nan(v["stop"]):
        return "—"
    return f"{fp(v['stop'])}（{v['stop_src']}，{fpct(-v['risk'] / v['close'] * 100)}）"


def target_txt(v) -> str:
    if nan(v["target"]):
        return "—"
    return f"{fp(v['target'])}（{'已突破·2R' if v['is_breakout'] else '近高'}）"


def rr_txt(x) -> str:
    if nan(x):
        return "—"
    return f"1:{x:.1f} " + ("划算" if x >= 2 else "不划算" if x < 1 else "一般")


def vol_txt(x) -> str:
    if nan(x):
        return "—"
    return f"{'放量' if x >= 1 else '缩量'} {x:.2f}x"


def rows_trend(r: Result) -> list[str]:
    if not r.ok:
        return [r.symbol, "数据缺失", "—", "—", "—", "—", "—", "—", "—", "—"]
    v = r.v
    return [r.symbol, fp(v["close"]), fpct(v["chg"], 2), v["pos_txt"], v["align_txt"], v["struct_txt"],
            vol_txt(v["vol_ratio"]), f"{v['rs_txt']} vs {r.bench}" if v["rs_txt"] != "无数据" else f"无数据（{r.bench}）",
            f"{fp(v['ll'])} / {fp(v['hh'])}", r.date]


def gap_txt(v) -> str:
    """与 Pine 表格一致：N 个；上方最近 X，下方最近 Y（没有缺口时为“无”）。"""
    if not v.get("gap_n"):
        return "无"
    up = "无" if nan(v["gap_above"]) else fp(v["gap_above"])
    dn = "无" if nan(v["gap_below"]) else fp(v["gap_below"])
    return f"{v['gap_n']} 个；上方最近 {up}，下方最近 {dn}"


def rows_risk(r: Result) -> list[str]:
    if not r.ok:
        return [r.symbol, "数据缺失"] + ["—"] * 9
    v = r.v
    return [r.symbol, fp(v["atr"]), dist_txt(v["d20p"], v["d20a"]), dist_txt(v["d50p"], v["d50a"]),
            pos52_txt(v["pos52"]), ud_txt(v["ud"]), atr_rank_txt(v["atr_rank"]), stop_txt(v), target_txt(v),
            rr_txt(v["rr"]), gap_txt(v)]


TREND_HEAD = ["代码", "收盘", "涨跌", "均线位置", "排列", "结构", "量能", "相对强弱", "近低 / 近高", "数据日期"]
RISK_HEAD = ["代码", "ATR14", "离MA20", "离MA50", "一年位置", "涨/跌量比", "ATR分位", "止损", "目标", "风险收益比", "未补缺口"]


def md_table(head, rows) -> str:
    esc = lambda s: str(s).replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    lines += ["| " + " | ".join(esc(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def build_markdown(results: list[Result], data_date: str) -> str:
    out = [f"# 观察池日报 {data_date}", "",
           f"数据日期：{data_date}（各标的最后一根已收盘日线，见表中“数据日期”列）。数据源 Yahoo Finance，公式与 `indicators/` 下两个 Pine 指标一致，纯固定公式、无 AI。",
           "", "## 今日变化", ""]
    any_change = False
    for r in results:
        if r.ok and r.changes:
            any_change = True
            out.append(f"- **{r.symbol}**：" + "；".join(t for _, t in r.changes))
    if not any_change:
        out.append("- 今日无新信号")
    missing = [r for r in results if not r.ok]
    if missing:
        out += ["", "数据缺失：" + "；".join(f"{r.symbol}（{r.error}）" for r in missing)]
    out += ["", "## 趋势与结构", "", md_table(TREND_HEAD, [rows_trend(r) for r in results]),
            "", "## 位置与风险", "", md_table(RISK_HEAD, [rows_risk(r) for r in results])]
    notes = [f"{r.symbol}：{'，'.join(r.notes)}" for r in results if r.ok and r.notes]
    if notes:
        out += ["", "数据不足：" + "；".join(notes) + "（与 Pine 一样，缺的均线按 na 处理）"]
    out += ["", "读法：结构 = 收盘对比前 20 根最高/最低；量能 = 当日量 / 20 日均量；相对强弱 = 收盘/基准 对比其 20 日均线；"
            "离均线括号内为 ATR 倍数（≥3 偏离大，≤1 贴近）；止损 = max(20 根最低, 收盘 − 2×ATR)；目标 = 20 根最高（已突破则按 2R）；"
            "未补缺口 = 最近 10 个未回补跳空缺口的个数，及收盘上方 / 下方最近的缺口边沿。",
            "", "> 不构成投资建议。仅为固定公式的机械计算结果，数据可能有延迟或错误。", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------
# 邮件 HTML —— 苹果式极简 + 少量 useLayouts 点缀（暖米白底、海军蓝字、一条渐变细条、等宽小标签）
# 信息层级：标题 → 今日变化 → 总览（一行一只）→ 每只明细（头行 / 重点行 / 次要列表）→ 页脚
# 只用表格布局 + 内联样式（渐变带纯色兜底），兼容 Gmail 网页 / Gmail App / iOS 邮件。
# ---------------------------------------------------------------------
FONT = ("-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',"
        "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',Arial,sans-serif")
MONO = "ui-monospace,Menlo,monospace"
C_PAGE = "#f5f3ee"     # 暖米白（useLayouts）
C_NAVY = "#071a31"     # 主文字（useLayouts）
C_GREY = "#7a7f87"     # 次要文字
C_LINE = "#ebe8e1"     # 细线 / 卡片边框
C_SOFT = "#f8f7f3"     # 重点行底色
C_BLUE = "#0071e3"     # 唯一强调色
C_UP, C_DN = "#c8463d", "#2f8a57"   # 红涨绿跌（柔和）
GRAD = "linear-gradient(90deg,#2c5086 0%,#7e8ac7 35%,#c39bdd 65%,#fcc0ad 100%)"  # 取自 useLayouts 头图
GRAD_FALLBACK = "#7e8ac7"
TONE_OF = {
    "多头排列": "up", "空头排列": "down", "均线纠缠": "flat",
    "突破近高": "up", "跌破近低": "down", "区间内": "flat",
    "偏强": "up", "偏弱": "down",
}
SHORT_TREND = {"多头排列": "多头", "空头排列": "空头", "均线纠缠": "纠缠"}

DARK_CSS = """
@media (prefers-color-scheme: dark){
 .pg{background:#121212 !important;}
 .cd{background:#1c1c1e !important;border-color:#2c2c2e !important;}
 .sf{background:#242426 !important;}
 .tx{color:#f2f2f2 !important;} .gy{color:#9a9ca1 !important;}
 .ln{border-color:#2c2c2e !important;}
 .up{color:#ff7b72 !important;} .dn{color:#5fd08f !important;} .ac{color:#4ea1ff !important;}
 .pl{background:#3a2e1c !important;color:#ffb35c !important;}
}
"""


def _tone(txt: str) -> tuple[str, str]:
    t = TONE_OF.get(txt, "flat")
    return {"up": (C_UP, "up"), "down": (C_DN, "dn")}.get(t, (C_NAVY, "tx"))


def _chg(x) -> tuple[str, str]:
    if nan(x) or x == 0:
        return C_GREY, "gy"
    return (C_UP, "up") if x > 0 else (C_DN, "dn")


def _pill(text: str) -> str:
    """唯一的标签样式，只在有含义时使用（偏离大等）。"""
    return (f'<span class="pl" style="display:inline-block;background:#fdf0e1;color:#a85a0c;border-radius:6px;'
            f'padding:0 6px;margin-left:6px;font-size:12px;line-height:18px;">{html.escape(text)}</span>')


def _label(text: str) -> str:
    """区块小标签（等宽、灰色、大写）。"""
    return (f'<div class="gy" style="font-family:{MONO};font-size:11px;letter-spacing:1.2px;text-transform:uppercase;'
            f'color:{C_GREY};padding:0 4px 8px;">{html.escape(text)}</div>')


T = '<table width="100%" cellspacing="0" cellpadding="0" border="0"'
CARD = f'class="cd" style="background:#ffffff;border:1px solid {C_LINE};border-radius:16px;"'


def _detail_card(r: Result, data_date: str, compact: bool = False) -> str:
    e = html.escape
    if not r.ok:
        return (f'{T} {CARD}><tr><td style="padding:18px 20px;">'
                f'<span class="tx" style="font-size:17px;font-weight:600;color:{C_NAVY};">{e(r.symbol)}</span>'
                f'<span class="gy" style="font-size:13px;color:{C_GREY};margin-left:8px;">数据缺失</span>'
                f'<div class="gy" style="font-size:13px;color:{C_GREY};margin-top:6px;">{e(r.error[:80])}</div>'
                f'</td></tr></table>')
    v = r.v
    name = (r.name or "").strip()
    if len(name) > 28:
        name = (name[:28].rsplit(" ", 1)[0].rstrip(" ,.-") or name[:28]) + "…"
    sub = name + (f" · {r.date}" if r.date != data_date else "")
    cc, ccls = _chg(v["chg"])
    dot = f'<span class="ac" style="color:{C_BLUE};font-size:10px;margin-left:6px;vertical-align:3px;">●</span>' if r.changes else ""

    # ① 头行
    head = (f'{T}><tr><td valign="top">'
            f'<div class="tx" style="font-size:17px;line-height:22px;font-weight:600;color:{C_NAVY};">{e(r.symbol)}{dot}</div>'
            f'<div class="gy" style="font-size:12px;line-height:18px;color:{C_GREY};margin-top:2px;">{e(sub) or "&nbsp;"}</div></td>'
            f'<td valign="top" align="right" style="text-align:right;white-space:nowrap;padding-left:12px;">'
            f'<div class="tx" style="font-size:17px;line-height:22px;font-weight:600;color:{C_NAVY};">{fp(v["close"])}</div>'
            f'<div class="{ccls}" style="font-size:14px;line-height:18px;font-weight:500;color:{cc};margin-top:2px;">{fpct(v["chg"], 2)}</div>'
            f'</td></tr></table>')

    # ② 重点行：趋势 / 结构 / 风险收益比 + 止损·目标
    tc, tcls = _tone(v["align_txt"])
    sc, scls = _tone(v["struct_txt"])
    rr = v["rr"]
    rr_val = "—" if nan(rr) else f"1 : {rr:.1f}"
    rcolor, rcls = (C_BLUE, "ac") if not nan(rr) and rr >= 2 else (C_NAVY, "tx")

    def key(label, value, color, cls, align="left"):
        return (f'<td width="33%" valign="top" align="{align}" style="width:33.33%;text-align:{align};">'
                f'<div class="gy" style="font-size:12px;line-height:16px;color:{C_GREY};">{label}</div>'
                f'<div class="{cls}" style="font-size:17px;line-height:22px;font-weight:600;color:{color};margin-top:3px;">{e(value)}</div></td>')
    stop_pct = "" if nan(v["stop"]) else f"（{fpct(-v['risk'] / v['close'] * 100)}）"
    tgt_note = "（已突破·2R）" if v["is_breakout"] else ""
    hero = (f'<div class="sf" style="background:{C_SOFT};border-radius:12px;padding:12px 14px;margin-top:14px;">'
            f'{T} style="table-layout:fixed;"><tr>'
            + key("趋势", v["align_txt"], tc, tcls) + key("结构", v["struct_txt"], sc, scls, "center")
            + key("风险收益比", rr_val, rcolor, rcls, "right") + "</tr></table>"
            f'<div class="ln gy" style="border-top:1px solid {C_LINE};margin-top:10px;padding-top:9px;font-size:14px;line-height:19px;color:{C_GREY};">'
            f'{T}><tr><td class="gy" style="color:{C_GREY};">止损 <b class="tx" style="color:{C_NAVY};font-weight:600;">{fp(v["stop"])}</b>{e(stop_pct)}</td>'
            f'<td class="gy" align="right" style="text-align:right;color:{C_GREY};">目标 <b class="tx" style="color:{C_NAVY};font-weight:600;">{fp(v["target"])}</b>{e(tgt_note)}</td>'
            f'</tr></table></div></div>')
    if compact:
        return f'{T} {CARD}><tr><td style="padding:18px 20px 18px;">{head}{hero}</td></tr></table>'

    # ③ 次要列表：左灰标签、右对齐数值
    def dist(p, a):
        if nan(p):
            return "—", ""
        s = fpct(p) + ("" if nan(a) else f" · {abs(a):.1f} ATR")
        return s, (_pill("偏离大") if not nan(a) and abs(a) >= 3 else "")
    d20, d20p = dist(v["d20p"], v["d20a"])
    d50, d50p = dist(v["d50p"], v["d50a"])
    vr = v["vol_ratio"]
    rows = [
        ("均线位置", e(v["pos_txt"])),
        ("量能", "—" if nan(vr) else f"{'放量' if vr >= 1 else '缩量'} {vr:.2f}×"),
        ("相对强弱", "—" if v["rs_txt"] == "无数据" else f'{e(v["rs_txt"])} <span class="gy" style="color:{C_GREY};">vs {e(r.bench)}</span>'),
        ("离 MA20", e(d20) + d20p),
        ("离 MA50", e(d50) + d50p),
        ("一年位置", e(pos52_txt(v["pos52"]).replace(" ", " · ")) + ("" if r.bars >= LEN52 else f'<span class="gy" style="color:{C_GREY};">（{r.bars} 根）</span>')),
        ("近低 / 近高", f'{fp(v["ll"])} / {fp(v["hh"])}'),
        ("ATR14", fp(v["atr"])),
        ("涨跌量比", e(ud_txt(v["ud"]).replace(" ", " · "))),
        ("ATR 分位", e(atr_rank_txt(v["atr_rank"]).replace(" ", " · "))),
        ("未补缺口", e(gap_short(v))),
    ]
    lst = "".join(
        f'<tr><td class="gy" style="padding:5px 0;color:{C_GREY};white-space:nowrap;">{k}</td>'
        f'<td class="tx" align="right" style="padding:5px 0 5px 12px;text-align:right;color:{C_NAVY};">{val}</td></tr>'
        for k, val in rows)
    note = ""
    if r.notes:
        note = f'<div class="gy" style="font-size:12px;line-height:17px;color:{C_GREY};margin-top:8px;">{e("，".join(r.notes))}</div>'
    return (f'{T} {CARD}><tr><td style="padding:18px 20px 14px;">{head}{hero}'
            f'{T} style="margin-top:10px;font-size:14px;line-height:19px;">{lst}</table>{note}'
            f'</td></tr></table>')


def gap_short(v) -> str:
    """邮件里一行放得下的写法：3 个 · 上 1,108.72 · 下 902.60（没有则“无”）。"""
    if not v.get("gap_n"):
        return "无"
    parts = [f"{v['gap_n']} 个"]
    parts.append("上 " + ("无" if nan(v["gap_above"]) else fp(v["gap_above"])))
    parts.append("下 " + ("无" if nan(v["gap_below"]) else fp(v["gap_below"])))
    return " · ".join(parts)


MAX_HTML_BYTES = 95_000  # Gmail 超过约 102KB 会折叠邮件，留出余量


def build_html(results: list[Result], data_date: str, gen_time: str) -> str:
    """完整卡片；若超过 MAX_HTML_BYTES，则从后往前把明细卡片换成精简版（只留头行和重点行）。"""
    compact: set[str] = set()
    out = _build_html(results, data_date, gen_time, compact)
    for r in reversed(results):
        if len(out.encode("utf-8")) <= MAX_HTML_BYTES:
            break
        compact.add(r.symbol)
        out = _build_html(results, data_date, gen_time, compact)
    if compact:
        print(f"[提示] 邮件较大，{len(compact)} 只标的使用精简卡片：{'、'.join(sorted(compact))}")
    return out


def _build_html(results: list[Result], data_date: str, gen_time: str, compact: set[str]) -> str:
    e = html.escape
    ok = [r for r in results if r.ok]
    changed = [r for r in ok if r.changes]
    missing = [r for r in results if not r.ok]
    n_sig = sum(len(r.changes) for r in ok)
    try:
        d = datetime.strptime(data_date, "%Y-%m-%d")
        date_cn = f"{d.year}年{d.month}月{d.day}日 周{'一二三四五六日'[d.weekday()]}"
    except ValueError:
        date_cn = data_date
    sp = lambda h: f'<tr><td style="height:{h}px;line-height:{h}px;font-size:0;">&nbsp;</td></tr>'  # noqa: E731
    rows: list[str] = []

    # 1. 标题
    rows.append(
        f'<tr><td style="padding:4px 4px 0;">{_label("Watchlist · Daily")}'
        f'<div class="tx" style="font-size:28px;line-height:34px;font-weight:600;letter-spacing:-.5px;color:{C_NAVY};">观察池日报</div>'
        f'<div class="gy" style="font-size:14px;line-height:20px;color:{C_GREY};margin-top:4px;">{e(date_cn)} · 美股收盘</div>'
        f'</td></tr>')
    rows.append(sp(24))

    # 2. 今日变化（顶部一条渐变细条，最醒目的区块）
    rows.append(f'<tr><td>{_label(f"今日变化 · {n_sig}" if n_sig else "今日变化")}</td></tr>')
    if changed:
        items = []
        for k, r in enumerate(changed):
            top = "" if k == 0 else f"border-top:1px solid {C_LINE};"
            phrases = []
            for kind, t in r.changes:
                c, cls = {"up": (C_UP, "up"), "down": (C_DN, "dn")}.get(kind, (C_NAVY, "tx"))
                phrases.append(f'<span class="{cls}" style="color:{c};">{e(t)}</span>')
            items.append(
                f'<tr><td class="ln tx" valign="top" width="88" style="width:88px;padding:13px 0;{top}'
                f'font-size:17px;line-height:22px;font-weight:600;color:{C_NAVY};">{e(r.symbol)}</td>'
                f'<td class="ln" valign="top" style="padding:13px 0;{top}font-size:17px;line-height:22px;">'
                + '<span class="gy" style="color:#c3c1bb;">、</span>'.join(phrases) + "</td></tr>")
        body = f"{T}>" + "".join(items) + "</table>"
    else:
        body = f'<div class="gy" style="font-size:14px;line-height:20px;color:{C_GREY};padding:14px 0;">今日无新信号，各标的状态延续</div>'
    if missing:
        body += (f'<div class="gy" style="font-size:13px;color:{C_GREY};padding:4px 0 12px;">数据缺失：'
                 f'{e("、".join(r.symbol for r in missing))}</div>')
    rows.append(
        f'<tr><td>{T} {CARD}><tr><td height="3" bgcolor="{GRAD_FALLBACK}" style="height:3px;line-height:3px;font-size:0;'
        f'background-color:{GRAD_FALLBACK};background-image:{GRAD};border-radius:16px 16px 0 0;">&nbsp;</td></tr>'
        f'<tr><td style="padding:6px 20px 6px;">{body}</td></tr></table></td></tr>')
    rows.append(sp(28))

    # 3. 总览：一行一只
    rows.append(f'<tr><td>{_label("总览")}</td></tr>')
    th = f'class="gy" style="padding:12px 0 8px;font-size:12px;line-height:16px;color:{C_GREY};font-weight:400;'
    ov = [f'<tr><td {th}text-align:left;" width="27%">代码</td><td {th}text-align:right;" width="24%">收盘</td>'
          f'<td {th}text-align:right;" width="21%">涨跌</td><td {th}text-align:right;" width="15%">趋势</td>'
          f'<td {th}text-align:right;" width="13%">R:R</td></tr>']
    for r in results:
        td = f'class="ln" style="padding:12px 0;border-top:1px solid {C_LINE};font-size:14px;line-height:20px;'
        if not r.ok:
            ov.append(f'<tr><td {td}font-weight:600;color:{C_NAVY};" class="tx">{e(r.symbol)}</td>'
                      f'<td colspan="4" {td}text-align:right;color:{C_GREY};">数据缺失</td></tr>')
            continue
        v = r.v
        cc, ccls = _chg(v["chg"])
        tc, tcls = _tone(v["align_txt"])
        rr = v["rr"]
        rr_txt_ = "—" if nan(rr) else f"{rr:.1f}"
        rc, rcls = (C_BLUE, "ac") if not nan(rr) and rr >= 2 else ((C_GREY, "gy") if not nan(rr) and rr < 1 else (C_NAVY, "tx"))
        mark = f'<span class="ac" style="color:{C_BLUE};font-size:9px;margin-left:4px;vertical-align:2px;">●</span>' if r.changes else ""
        ov.append(
            f'<tr><td {td}"><span class="tx" style="font-weight:600;color:{C_NAVY};">{e(r.symbol)}</span>{mark}</td>'
            f'<td {td}text-align:right;"><span class="tx" style="color:{C_NAVY};">{fp(v["close"])}</span></td>'
            f'<td {td}text-align:right;"><span class="{ccls}" style="color:{cc};">{fpct(v["chg"], 2)}</span></td>'
            f'<td {td}text-align:right;"><span class="{tcls}" style="color:{tc};">{SHORT_TREND.get(v["align_txt"], "—")}</span></td>'
            f'<td {td}text-align:right;"><span class="{rcls}" style="color:{rc};">{rr_txt_}</span></td></tr>')
    rows.append(
        f'<tr><td>{T} {CARD}><tr><td style="padding:2px 20px 4px;">'
        f'{T} style="table-layout:fixed;">' + "".join(ov) + '</table></td></tr></table>'
        f'<div class="gy" style="font-size:12px;line-height:17px;color:{C_GREY};padding:8px 4px 0;">'
        f'趋势 = 均线排列 · R:R = 风险收益比 · <span style="color:{C_BLUE};">●</span> 今日有信号</div></td></tr>')
    rows.append(sp(28))

    # 4. 明细
    rows.append(f'<tr><td>{_label("明细")}</td></tr>')
    for k, r in enumerate(results):
        if k:
            rows.append(sp(12))
        rows.append(f"<tr><td>{_detail_card(r, data_date, r.symbol in compact)}</td></tr>")
    rows.append(sp(28))

    # 5. 页脚
    rows.append(
        f'<tr><td align="center" class="gy" style="padding:0 12px;font-size:12px;line-height:19px;color:{C_GREY};text-align:center;">'
        f'<span style="white-space:nowrap;">数据日期 {e(data_date)}</span> · <span style="white-space:nowrap;">Yahoo Finance</span> · '
        f'<span style="white-space:nowrap;">生成于 {e(gen_time)} 北京时间</span><br>'
        f'固定公式计算 · 红涨绿跌 · <span class="tx" style="color:{C_NAVY};">不构成投资建议</span></td></tr>')

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        f'<title>观察池日报 {e(data_date)}</title><style>{DARK_CSS}</style></head>'
        f'<body class="pg" style="margin:0;padding:0;background:{C_PAGE};-webkit-text-size-adjust:100%;">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">'
        f'{e(data_date)} · 今日变化 {n_sig} 条</div>'
        f'{T} class="pg" bgcolor="{C_PAGE}" style="background:{C_PAGE};"><tr><td align="center" style="padding:28px 14px 36px;">'
        f'{T} style="max-width:600px;width:100%;font-family:{FONT};color:{C_NAVY};font-variant-numeric:tabular-nums;">'
        + "".join(rows) +
        '</table></td></tr></table></body></html>')


# =====================================================================
# 观察池 / 邮件 / 主流程
# =====================================================================
def run_now() -> datetime:
    """当前时间；可用环境变量 SCAN_NOW（ISO 格式，带时区）模拟运行时刻，便于测试。"""
    raw = os.environ.get("SCAN_NOW", "").strip()
    if raw:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=BJ)
    return datetime.now(BJ)


def expected_us_session(now: datetime) -> tuple[str, bool | None, str]:
    """返回 (最近一个已收盘的美股工作日日期, 该日是否 NYSE 交易日, 日历来源说明)。

    做法：在纽约时间里往回找最近一个“收盘时间已过”的工作日（周一至周五）；
    再用 exchange_calendars 的 XNYS 日历判断它是不是交易日（节假日休市则为 False）。
    日历不可用或超出范围时为 None，交给“数据日期”兜底检查。
    """
    ny = ZoneInfo("America/New_York")
    now_ny = now.astimezone(ny)
    try:
        import exchange_calendars as xc
        cal = xc.get_calendar("XNYS")
    except Exception as ex:  # noqa: BLE001
        print(f"[警告] 交易日历不可用：{ex}", file=sys.stderr)
        cal = None
    d = now_ny.date()
    for _ in range(10):
        if d.weekday() < 5:
            is_sess = None
            close_dt = datetime(d.year, d.month, d.day, 16, 0, tzinfo=ny)
            if cal is not None:
                try:
                    is_sess = bool(cal.is_session(str(d)))
                    if is_sess:  # 提前收盘日（如感恩节次日 13:00）用真实收盘时间
                        close_dt = cal.session_close(str(d)).to_pydatetime().astimezone(ny)
                except Exception:  # noqa: BLE001  超出日历范围
                    is_sess = None
            if now_ny >= close_dt + CLOSE_BUFFER:
                return str(d), is_sess, ("XNYS 日历" if is_sess is not None else "无日历，按数据日期判断")
        d -= timedelta(days=1)
    return str(d), None, "无日历"


def scan_md_date(path: Path) -> str:
    """读取现有 scan.md 第一行里的数据日期（# 观察池日报 YYYY-MM-DD）。"""
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return ""
    return first.replace("# 观察池日报", "").strip()


def gate_check(results: list[Result], now: datetime, md_path: Path) -> tuple[bool, str]:
    """是否需要更新 scan.md 并发信。返回 (继续?, 说明)。"""
    session, is_sess, src = expected_us_session(now)
    if is_sess is False:
        return False, f"上一个美股交易日 {session} 休市（{src}），无新数据，跳过"
    us = [r for r in results if r.ok and r.tz == "America/New_York"]
    if us:
        newest = max(r.date for r in us)
        if newest != session:
            return False, f"上一个美股交易日 {session} 无新数据（美股最新日线为 {newest}），跳过"
        data_date = newest
    else:
        data_date = max(r.date for r in results if r.ok)
    prev = scan_md_date(md_path)
    if prev == data_date:
        return False, f"scan.md 已是 {data_date} 的数据（已发送过），跳过；需要重发请用 force"
    return True, f"上一个美股交易日 {session}（{src}），数据日期 {data_date}，生成日报"


def read_watchlist(path: Path) -> list[tuple[str, str]]:
    items = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        sym = parts[0].upper() if not parts[0].startswith("^") else parts[0]
        bench = parts[1] if len(parts) > 1 and parts[1] else DEFAULT_BENCH
        if sym:
            items.append((sym, bench))
    return items


def send_email(subject: str, html_body: str, text_body: str) -> str:
    user = os.environ.get("GMAIL_USER", "").strip()
    pwd = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to = os.environ.get("MAIL_TO", "").strip()
    missing = [k for k, val in (("GMAIL_USER", user), ("GMAIL_APP_PASSWORD", pwd), ("MAIL_TO", to)) if not val]
    if missing:
        return "skip:" + ",".join(missing)
    recipients = [x.strip() for x in to.split(",") if x.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pwd.replace(" ", ""))
        s.sendmail(user, recipients, msg.as_string())
    return "sent"


def main() -> int:
    ap = argparse.ArgumentParser(description="观察池日报（固定公式）")
    ap.add_argument("--no-email", action="store_true", help="只写文件，不发邮件")
    ap.add_argument("--watchlist", default=str(WATCHLIST))
    ap.add_argument("--force", action="store_true",
                    help="跳过“休市/无新数据/重复发送”检查，强制生成并发信（也可用环境变量 FORCE=true）")
    args = ap.parse_args()

    items = read_watchlist(Path(args.watchlist))
    if not items:
        print("观察池为空", file=sys.stderr)
        return 1

    bench_cache: dict[str, pd.Series | None] = {}
    results: list[Result] = []
    for sym, bench in items:
        if bench not in bench_cache:
            try:
                bench_cache[bench] = fetch_daily(bench)["Close"]
            except Exception as ex:  # noqa: BLE001
                print(f"[警告] 基准 {bench}：{ex}", file=sys.stderr)
                bench_cache[bench] = None
        try:
            df = fetch_daily(sym)
            r = compute(sym, df, bench_cache[bench], bench)
            r.name, r.tz = df.attrs.get("name", ""), df.attrs.get("tz", "")
            if bench_cache[bench] is None:
                r.notes.append(f"基准 {bench} 数据缺失")
        except Exception as ex:  # noqa: BLE001
            r = Result(symbol=sym, bench=bench, ok=False, error=str(ex)[:120])
            print(f"[警告] {sym}：{ex}", file=sys.stderr)
        results.append(r)
        print(f"{sym:10s} {'OK' if r.ok else '缺失'} {r.date} bars={r.bars}")

    ok = [r for r in results if r.ok]
    if not ok:
        print("全部标的获取失败", file=sys.stderr)
        return 1

    force = args.force or os.environ.get("FORCE", "").strip().lower() in ("1", "true", "yes")
    now = run_now()
    go, why = gate_check(results, now, SCAN_MD)
    if not go and not force:
        print(why)
        return 0
    print(why if go else f"{why}——已指定 force，继续")

    # 数据日期以美股为准（与跳过检查一致）；观察池里没有美股时取最新日期
    us_dates = [r.date for r in ok if r.tz == "America/New_York"]
    data_date = max(us_dates) if us_dates else max(r.date for r in ok)
    gen_time = now.astimezone(BJ).strftime("%Y-%m-%d %H:%M")
    md = build_markdown(results, data_date)
    SCAN_MD.write_text(md, encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_body = build_html(results, data_date, gen_time)
    (OUT_DIR / "email.html").write_text(html_body, encoding="utf-8")
    print(f"已写入 {SCAN_MD} 和 {OUT_DIR / 'email.html'}")

    if args.no_email:
        print("已按参数跳过发信")
        return 0
    subject = f"观察池日报 {data_date}"
    try:
        status = send_email(subject, html_body, md)
    except Exception as ex:  # noqa: BLE001
        print(f"[错误] 发信失败：{ex}", file=sys.stderr)
        return 2
    if status.startswith("skip:"):
        print(f"未配置 {status[5:]}，跳过发信")
    else:
        print(f"邮件已发送：{subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
