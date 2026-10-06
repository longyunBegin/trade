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
def fetch_daily(symbol: str, period: str = "2y", retries: int = 3) -> pd.DataFrame:
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            tk = yf.Ticker(symbol)
            df = tk.history(period=period, interval="1d", auto_adjust=False, actions=False)
            if df is None or df.empty:
                raise ValueError("无数据")
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
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


def rows_risk(r: Result) -> list[str]:
    if not r.ok:
        return [r.symbol, "数据缺失"] + ["—"] * 8
    v = r.v
    return [r.symbol, fp(v["atr"]), dist_txt(v["d20p"], v["d20a"]), dist_txt(v["d50p"], v["d50a"]),
            pos52_txt(v["pos52"]), ud_txt(v["ud"]), atr_rank_txt(v["atr_rank"]), stop_txt(v), target_txt(v),
            rr_txt(v["rr"])]


TREND_HEAD = ["代码", "收盘", "涨跌", "均线位置", "排列", "结构", "量能", "相对强弱", "近低 / 近高", "数据日期"]
RISK_HEAD = ["代码", "ATR14", "离MA20", "离MA50", "一年位置", "涨/跌量比", "ATR分位", "止损", "目标", "风险收益比"]


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
            "离均线括号内为 ATR 倍数（≥3 偏离大，≤1 贴近）；止损 = max(20 根最低, 收盘 − 2×ATR)；目标 = 20 根最高（已突破则按 2R）。",
            "", "> 不构成投资建议。仅为固定公式的机械计算结果，数据可能有延迟或错误。", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------
# 邮件 HTML —— useLayouts 风格（uselayouts.com）：
#   暖米白底 #f5f3ee、深海军蓝文字 #071a31、细边框白色圆角卡片 + 内嵌“媒体”色块、
#   海军蓝→蓝→淡紫/蜜桃渐变头图、Bento 不等宽小格、等宽字体大写小标签、彩色计数胶囊。
# 只用表格布局 + 内联样式（渐变都带纯色兜底），兼容 Gmail 网页 / Gmail App / iOS 邮件。
# ---------------------------------------------------------------------
FONT = ("Geist,-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',"
        "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',Arial,sans-serif")
MONO = "ui-monospace,Menlo,monospace"
# 取自 uselayouts.com 的页面 CSS / 计算样式 / 头图像素
C_PAGE = "#f5f3ee"      # 页面暖米白
C_SOFT = "#f9f8f6"      # 浅格底
C_NAVY = "#071a31"      # 标题/主文字
C_BODY = "#4b565e"      # 正文灰
C_CHIPTX = "#3d464c"    # 标签文字
C_CHIPBG = "#f2f3f4"    # 标签底
C_LINE = "#e2e2e2"      # 细边框
C_MUTED = "#9f9f9f"     # 弱文字
C_FOOT = "#acafb9"      # 页脚文字
C_DARK = "#1b1c1d"      # 深色块
C_BLUE = "#3351e5"      # 主按钮蓝
C_SKY = "#2495d1"       # 计数胶囊·蓝
C_SAGE = "#879f6c"      # 计数胶囊·绿（用作“跌”）
C_TERRA = "#bc6147"     # 计数胶囊·赤陶（用作“涨”）
C_RASP = "#b6547a"      # 计数胶囊·莓红
UP_TX, DN_TX = "#b5523a", "#5e7b45"            # 白底上的涨/跌文字（红涨绿跌，按配色调柔）
UP_TX_D, DN_TX_D = "#f2937c", "#a9c98c"        # 深底上的涨/跌文字
HERO_GRAD = ("linear-gradient(168deg,#0b2745 0%,#0d2c51 16%,#2c5086 36%,#7e8ac7 54%,"
             "#c39bdd 66%,#efb7ba 80%,#fcc0ad 100%)")
HERO_FALLBACK = "#1d3a66"
PASTEL_GRAD = "linear-gradient(135deg,#aca6f8 0%,#c5a2f0 30%,#e3b0de 62%,#fdc3a9 100%)"
PASTEL_FALLBACK = "#e2c4ea"

DOT = {"up": C_TERRA, "down": C_SAGE, "accent": C_SKY, "warn": C_RASP, "flat": "#bababb"}
TONE_OF = {
    "多头排列": "up", "空头排列": "down", "均线纠缠": "flat",
    "价在三线上方": "up", "价在三线下方": "down", "夹在均线间": "flat",
    "突破近高": "up", "跌破近低": "down", "区间内": "flat",
    "偏强": "up", "偏弱": "down", "无数据": "flat",
    "放量": "accent", "缩量": "flat",
    "偏离大": "warn", "贴近": "accent", "正常": "flat",
    "高位": "up", "低位": "down", "中间": "flat",
    "买盘主导": "up", "卖盘主导": "down", "均衡": "flat",
    "收缩": "accent", "扩张": "warn",
    "划算": "accent", "一般": "flat", "不划算": "warn",
}

DARK_CSS = """
@media (prefers-color-scheme: dark){
 .pg{background:#111213 !important;}
 .cd{background:#1b1c1d !important;border-color:#2c2d30 !important;}
 .tl{background:#232427 !important;border-color:#2f3034 !important;}
 .ch{background:#2a2b2f !important;border-color:#36373b !important;color:#d4d6dc !important;}
 .tx{color:#f5f3ee !important;} .bd{color:#b9bec4 !important;} .mu{color:#8b8e96 !important;}
 .hd{background:#0e0f11 !important;}
 .up{color:#f2937c !important;} .dn{color:#a9c98c !important;}
}
"""


def _mono(text: str, size: int = 10, color: str = C_MUTED, cls: str = "mu", spacing: float = 1.2) -> str:
    return (f'<span class="{cls}" style="font-family:{MONO};font-size:{size}px;letter-spacing:{spacing}px;'
            f'text-transform:uppercase;color:{color};">{html.escape(text)}</span>')


def _chip(text: str, tone: str | None = None, dark: bool = False) -> str:
    """useLayouts 式等宽小标签：浅灰底 + 细边框 + 6px 圆角；前面的小圆点表示含义（红涨绿跌等）。"""
    dot = ""
    if tone is not False:
        t = tone or TONE_OF.get(text, "flat")
        dot = f'<b style="color:{DOT[t]};font-size:9px">●</b> '
    if dark:
        style = "background:#2a2b2f;border:1px solid #393a3f;color:#e6e6e8;"
        cls = ""
    else:
        style = f"background:{C_CHIPBG};border:1px solid {C_LINE};color:{C_CHIPTX};"
        cls = ' class="ch"'
    return (f'<span{cls} style="display:inline-block;{style}border-radius:6px;padding:2px 7px;margin:2px 3px 2px 0;'
            f'font:11px/17px {MONO}">{dot}{html.escape(text)}</span>')


def _badge(text: str, bg: str) -> str:
    """彩色计数胶囊（白色等宽字）。"""
    return (f'<span style="display:inline-block;background:{bg};color:#ffffff;border-radius:99px;padding:1px 8px;'
            f'font:600 11px/18px {MONO};white-space:nowrap;">{html.escape(text)}</span>')


def _chg_color(x, dark: bool = False) -> tuple[str, str]:
    if nan(x) or x == 0:
        return (C_FOOT if dark else C_MUTED), "mu"
    if x > 0:
        return (UP_TX_D if dark else UP_TX), "up"
    return (DN_TX_D if dark else DN_TX), "dn"


TILE_STYLE = f"background:{C_SOFT};border:1px solid #ebe9e3;border-radius:12px;padding:10px 11px"


def _tile(label: str, value: str, extra: str = "", color: str = C_NAVY, cls: str = "tx") -> tuple[str, str, str]:
    """Bento 小格：等宽小标签 + 读数 + 补充（value/extra 为已转义 HTML）。返回 (class, style, 内容)。"""
    inner = (f'<div class="mu" style="font:10px/14px {MONO};color:{C_MUTED}">{html.escape(label)}</div>'
             f'<div class="{cls}" style="font-size:16px;font-weight:600;{"" if color == C_NAVY else "color:" + color + ";"}margin:3px 0 1px">{value}</div>'
             + (f'<div>{extra}</div>' if extra else ""))
    return "tl", TILE_STYLE, inner


def _row(tiles: list[tuple[tuple[str, str, str], int]], gap: int = 6) -> str:
    """一行 Bento：[((class, style, 内容), 宽度百分比), ...]。
    小格本身就是 <td>（同一行自动等高），格与格之间用 6px 空白列隔开。"""
    tds = []
    for k, ((cls, style, inner), w) in enumerate(tiles):
        if k:
            tds.append(f'<td width="{gap}" style="width:{gap}px;font-size:0">&nbsp;</td>')
        tds.append(f'<td class="{cls}" width="{w}%" valign="top" style="{style}">{inner}</td>')
    return ('<table width="100%" cellspacing="0" cellpadding="0" '
            f'style="table-layout:fixed;margin-top:{gap}px"><tr>' + "".join(tds) + "</tr></table>")


def _small(text: str) -> str:
    return f'<span class="bd" style="font-size:12px;color:{C_BODY}">{html.escape(text)}</span>'


def _tag(text: str | None) -> str:
    return _chip(text) if text else ""


CARD = f'class="cd" style="background:#ffffff;border:1px solid {C_LINE};border-radius:18px;"'


def _ticker_card(r: Result, compact: bool = False) -> str:
    e = html.escape
    if not r.ok:
        return (f'<table width="100%" cellspacing="0" cellpadding="0" {CARD}><tr>'
                f'<td style="padding:16px 18px;"><span class="tx" style="font-size:18px;font-weight:600;color:{C_NAVY};">{e(r.symbol)}</span> '
                f'&nbsp;{_badge("数据缺失", C_RASP)}<div class="bd" style="font-size:12px;color:{C_BODY};margin-top:6px;">{e(r.error[:80])}</div>'
                f'</td></tr></table>')
    v = r.v
    name = (r.name or "").strip()
    if len(name) > 26:  # 名称过长时在词边界截断
        cut = name[:26].rsplit(" ", 1)[0].rstrip(" ,.-")
        name = (cut or name[:26]) + "…"
    badge_bg = C_MUTED if nan(v["chg"]) or v["chg"] == 0 else (C_TERRA if v["chg"] > 0 else C_SAGE)
    sig = ""
    if r.changes:
        sig = (f'<div style="margin-top:12px;">{_mono("今日信号", 10, "#bababb", "", 1.2)}<br>'
               + "".join(_chip(t, k, dark=True) for k, t in r.changes) + "</div>")
    # 深色“媒体”头块：代码 / 名称 / 收盘 / 涨跌胶囊
    head = (
        f'<div class="hd" style="background:{C_DARK};border-radius:12px;padding:16px 16px 14px;">'
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td valign="top"><div style="font-family:{MONO};font-size:10px;letter-spacing:1.2px;color:#bababb;line-height:14px;">'
        f'{e(name.upper()) if name else "&nbsp;"}</div>'
        f'<div style="font-size:24px;line-height:30px;font-weight:500;letter-spacing:-.4px;color:#ffffff;margin-top:4px;">{e(r.symbol)}</div></td>'
        f'<td valign="top" align="right" style="text-align:right;white-space:nowrap;padding-left:10px;">'
        f'<div style="font-size:24px;line-height:30px;font-weight:500;letter-spacing:-.4px;color:#ffffff;margin-top:18px;">{fp(v["close"])}</div>'
        f'<div style="margin-top:4px;">{_badge(fpct(v["chg"], 2), badge_bg)}</div></td>'
        f'</tr></table>{sig}</div>')
    # 状态标签
    rs_chip = _chip(f"{v['rs_txt']} vs {r.bench}", TONE_OF[v["rs_txt"]]) if v["rs_txt"] != "无数据" else ""
    chips = _chip(v["align_txt"]) + _chip(v["struct_txt"]) + rs_chip

    def split_tag(txt: str) -> tuple[str, str | None]:
        if txt == "—" or " " not in txt:
            return txt, None
        a, b = txt.split(" ", 1)
        return a, b

    def tone_text(txt: str) -> tuple[str, str]:
        t = TONE_OF.get(txt, "flat")
        return {"up": (UP_TX, "up"), "down": (DN_TX, "dn")}.get(t, (C_NAVY, "tx"))

    vol_tag = None if nan(v["vol_ratio"]) else ("放量" if v["vol_ratio"] >= 1 else "缩量")
    vol_val = "—" if nan(v["vol_ratio"]) else f"{v['vol_ratio']:.2f}×"
    d20_tag = None if nan(v["d20a"]) else ("偏离大" if abs(v["d20a"]) >= 3 else "贴近" if abs(v["d20a"]) <= 1 else "正常")
    pos_val, pos_tag = split_tag(pos52_txt(v["pos52"]))
    rr_val, rr_tag = split_tag(rr_txt(v["rr"]))
    rr_val = rr_val.replace(":", " : ")
    sc, scls = tone_text(v["struct_txt"])
    rc, rcls = tone_text(v["rs_txt"])
    stop_x = "" if nan(v["stop"]) else f"{v['stop_src']} · 距现价 {fpct(-v['risk'] / v['close'] * 100)}"
    tgt_x = "" if nan(v["target"]) else ("已突破近高 · 按 2R" if v["is_breakout"] else "近 20 根最高")
    slash = f'<span class="mu" style="color:{C_MUTED};font-weight:400"> / </span>'
    if compact:  # 邮件过大时的精简卡片：只保留头块、状态标签和一行关键数字
        line = " · ".join(f'<span style="white-space:nowrap">{e(t)}</span>' for t in [
            f"止损 {fp(v['stop'])}", f"目标 {fp(v['target'])}", f"风险收益比 {rr_val}",
            f"离MA20 {fpct(v['d20p'])}", f"一年位置 {pos52_txt(v['pos52'])}", r.date])
        return (f'<table width="100%" cellspacing="0" cellpadding="0" {CARD}><tr><td style="padding:8px;">{head}'
                f'<div style="padding:10px 4px 2px;">{chips}</div>'
                f'<div class="bd" style="font-size:12px;line-height:19px;color:{C_BODY};padding:4px 4px 4px;">{line}</div>'
                f'</td></tr></table>')
    grid = (
        _row([(_tile("趋势", e(v["pos_txt"]), _small("MA20 / 50 / 200")), 60),
              (_tile("结构", e(v["struct_txt"]), _small("对比前 20 根"), sc, scls), 40)])
        + _row([(_tile("量能", vol_val, _tag(vol_tag)), 33),
                (_tile(f"相对 {r.bench}", e(v["rs_txt"]), "", rc, rcls), 34),
                (_tile("一年位置", e(pos_val), _tag(pos_tag)), 33)])
        + _row([(_tile("离MA20", fpct(v["d20p"]), _tag(d20_tag) + ("" if nan(v["d20a"]) else _small(f"{v['d20a']:+.1f} ATR"))), 50),
                (_tile("风险收益比", e(rr_val), _tag(rr_tag)), 50)])
        + _row([(_tile("止损", fp(v["stop"]), _small(stop_x) if stop_x else ""), 50),
                (_tile("目标", fp(v["target"]), _small(tgt_x) if tgt_x else ""), 50)])
        + _row([(_tile("近低 / 近高 · 20根", f'{fp(v["ll"])}{slash}{fp(v["hh"])}'), 100)])
    )
    foot = " · ".join(e(t).replace(" ", "&nbsp;") for t in [
        r.date, f"ATR14 {fp(v['atr'])}", f"离MA50 {fpct(v['d50p'])}", f"涨跌量比 {fp(v['ud'])}",
        f"ATR分位 {'—' if nan(v['atr_rank']) else format(v['atr_rank'], '.0f') + '%'}"])
    note = ("<br>" + e("，".join(r.notes))) if r.notes else ""
    return (
        f'<table width="100%" cellspacing="0" cellpadding="0" {CARD}>'
        f'<tr><td style="padding:8px;">{head}'
        f'<div style="padding:10px 4px 2px;">{chips}</div>{grid}'
        f'<div class="mu" style="font:10px/16px {MONO};color:{C_MUTED};padding:10px 4px 4px;">{foot}{note}</div>'
        f'</td></tr></table>')


MAX_HTML_BYTES = 95_000  # Gmail 超过约 102KB 会折叠邮件，留出余量


def build_html(results: list[Result], data_date: str, gen_time: str) -> str:
    """完整卡片；若超过 MAX_HTML_BYTES，则从后往前把卡片换成精简版，直到不超限。"""
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
    n_up = sum(1 for r in ok if not nan(r.v["chg"]) and r.v["chg"] > 0)
    n_dn = sum(1 for r in ok if not nan(r.v["chg"]) and r.v["chg"] < 0)
    n_sig = sum(len(r.changes) for r in ok)
    changed = [r for r in ok if r.changes]
    missing = [r for r in results if not r.ok]
    try:
        d = datetime.strptime(data_date, "%Y-%m-%d")
        date_cn = f"{d.year}年{d.month}月{d.day}日 周{'一二三四五六日'[d.weekday()]}"
    except ValueError:
        date_cn = data_date
    sp = lambda h: f'<tr><td style="height:{h}px;line-height:{h}px;font-size:0;">&nbsp;</td></tr>'  # noqa: E731
    T = '<table width="100%" cellspacing="0" cellpadding="0"'
    rows: list[str] = []

    # ① 渐变头图（海军蓝 → 蓝 → 淡紫 / 蜜桃），无渐变的客户端显示海军蓝纯色
    syms = "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,.62);color:{C_NAVY};border-radius:99px;'
        f'padding:2px 9px;margin:3px 4px 0 0;font:11px/17px {MONO};">{e(r.symbol)}</span>'
        for r in results)
    rows.append(
        f'<tr><td>{T} bgcolor="{HERO_FALLBACK}" style="background-color:{HERO_FALLBACK};background-image:{HERO_GRAD};'
        f'border-radius:18px;"><tr><td style="padding:22px 22px 20px;">'
        f'<span style="display:inline-block;background:#ffffff;color:#000000;border-radius:3px;padding:3px 7px;'
        f'font-family:{MONO};font-size:10px;line-height:13px;letter-spacing:.6px;">&#9650; WATCHLIST // {e(data_date)}<br>DAILY CLOSE SCAN</span>'
        f'<div style="font-size:36px;line-height:42px;font-weight:500;letter-spacing:-1px;color:#ffffff;margin-top:18px;">观察池日报</div>'
        f'<div style="font-size:15px;line-height:23px;color:#ffffff;opacity:.85;margin-top:8px;">{e(date_cn)} · 收盘数据<br>'
        f'固定公式扫描 · 与 TradingView 指标同算法</div>'
        f'<div style="margin-top:18px;"><a href="https://github.com/longyunBegin/trade/blob/main/scan.md" '
        f'style="display:inline-block;background:{C_BLUE};color:#ffffff;text-decoration:none;border-radius:12px;'
        f'padding:9px 16px;font-size:14px;font-weight:500;">查看 scan.md</a></div>'
        f'<div style="height:64px;line-height:64px;font-size:0;">&nbsp;</div>'
        f'<div style="font-family:{MONO};font-size:10px;letter-spacing:1px;color:#ffffff;margin-bottom:4px;">'
        f'WATCHING {len(results)} TICKERS</div>{syms}'
        f'</td></tr></table></td></tr>')
    rows.append(sp(10))

    # ② Bento 概览：深色宽格 + 两个白格
    def stat_tile(label, num, color, cls):
        return ("cd", f"background:#ffffff;border:1px solid {C_LINE};border-radius:16px;padding:14px 12px",
                f'{_mono(label)}<div class="{cls}" style="font-size:30px;line-height:36px;font-weight:500;color:{color};margin-top:6px">{num}</div>')
    sig_tile = ("hd", f"background:{C_DARK};border:1px solid {C_DARK};border-radius:16px;padding:14px",
                f'{_mono("New signals", 10, "#bababb", "", 1.2)}'
                f'<div style="font-size:30px;line-height:36px;font-weight:500;color:#ffffff;margin-top:6px">{n_sig}'
                f'<span style="font-size:13px;color:#bababb;font-weight:400"> 条 · {len(changed)} 只</span></div>')
    rows.append(f"<tr><td>{_row([(sig_tile, 50), (stat_tile('上涨', n_up, UP_TX, 'up'), 25), (stat_tile('下跌', n_dn, DN_TX, 'dn'), 25)], 8)}</td></tr>")
    rows.append(sp(10))

    # ③ 今日变化：白色外框 + 淡彩渐变“媒体”块 + 计数胶囊标题 + 等宽标签
    if changed:
        lines = []
        for k, r in enumerate(changed):
            top = "" if k == 0 else "border-top:1px solid rgba(7,26,49,.10);"
            lines.append(
                f'<tr><td valign="top" width="74" style="width:74px;padding:10px 0 7px;{top}">'
                f'<span style="font-size:15px;font-weight:600;color:{C_NAVY};">{e(r.symbol)}</span></td>'
                f'<td valign="top" style="padding:8px 0 5px;{top}">'
                + "".join(
                    f'<span style="display:inline-block;background:#ffffff;color:{C_NAVY};border-radius:6px;padding:2px 8px;'
                    f'margin:2px 4px 2px 0;font:11px/17px {MONO};white-space:nowrap;">'
                    f'<b style="color:{DOT[kk]};font-size:9px">●</b> {e(t)}</span>'
                    for kk, t in r.changes) + "</td></tr>")
        inner = f'{T}>' + "".join(lines) + "</table>"
    else:
        inner = f'<div style="font-size:15px;color:{C_NAVY};padding:6px 0;">今日无新信号，各标的状态延续。</div>'
    if missing:
        inner += (f'<div style="font-size:12px;color:{C_NAVY};padding-top:8px;">数据缺失：'
                  f'{e("、".join(r.symbol for r in missing))}</div>')
    rows.append(
        f'<tr><td>{T} {CARD}><tr><td style="padding:8px;">'
        f'{T} bgcolor="{PASTEL_FALLBACK}" style="background-color:{PASTEL_FALLBACK};background-image:{PASTEL_GRAD};border-radius:12px;">'
        f'<tr><td style="padding:14px 16px 12px;">{inner}</td></tr></table>'
        f'<div style="padding:12px 6px 4px;">{_badge(str(n_sig), C_TERRA if n_sig else C_MUTED)}'
        f'<span class="tx" style="font-size:19px;font-weight:500;color:{C_NAVY};vertical-align:middle;margin-left:8px;">今日变化</span></div>'
        f'<div style="padding:4px 6px 4px;">{_chip("结构突破/跌破", False)}{_chip("穿越 MA20/50/200", False)}'
        f'{_chip("排列变化", False)}{_chip("相对强弱", False)}</div>'
        f'</td></tr></table></td></tr>')
    rows.append(sp(34))

    # ④ 区块标题
    rows.append(
        f'<tr><td style="padding:0 4px;">{_mono("Watchlist · " + str(len(results)))}'
        f'<div class="tx" style="font-size:28px;line-height:34px;font-weight:500;letter-spacing:-.6px;color:{C_NAVY};margin-top:8px;">全部标的</div>'
        f'<div class="bd" style="font-size:14px;line-height:21px;color:{C_BODY};margin-top:6px;">'
        f'趋势 · 结构 · 量能 · 位置与风险 · 红涨绿跌</div></td></tr>')
    rows.append(sp(16))

    # ⑤ 每只标的
    for k, r in enumerate(results):
        if k:
            rows.append(sp(12))
        rows.append(f"<tr><td>{_ticker_card(r, r.symbol in compact)}</td></tr>")
    rows.append(sp(16))

    # ⑥ 深色页脚
    rows.append(
        f'<tr><td>{T} class="hd" bgcolor="{C_DARK}" style="background:{C_DARK};border-radius:18px;"><tr>'
        f'<td style="padding:20px 22px;font-size:12px;line-height:20px;color:{C_FOOT};">'
        f'<div style="font-size:15px;color:#ffffff;font-weight:500;margin-bottom:6px;">不构成投资建议</div>'
        f'<span style="white-space:nowrap;">数据日期 {e(data_date)}</span> · <span style="white-space:nowrap;">数据源 Yahoo Finance</span><br>'
        f'<span style="white-space:nowrap;">生成于 {e(gen_time)} 北京时间</span> · <span style="white-space:nowrap;">红涨绿跌</span><br>'
        f'固定公式机械计算，数据可能有延迟或错误。'
        f'<div style="font-family:{MONO};font-size:10px;letter-spacing:1px;color:#6f727a;margin-top:12px;">'
        f'LONGYUNBEGIN / TRADE · WATCHLIST SCAN</div>'
        f'</td></tr></table></td></tr>')

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        f'<title>观察池日报 {e(data_date)}</title><style>{DARK_CSS}</style></head>'
        f'<body class="pg" style="margin:0;padding:0;background:{C_PAGE};-webkit-text-size-adjust:100%;">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">'
        f'{e(data_date)} · 上涨 {n_up} · 下跌 {n_dn} · 新信号 {n_sig}</div>'
        f'{T} class="pg" bgcolor="{C_PAGE}" style="background:{C_PAGE};"><tr><td align="center" style="padding:16px 12px 28px;">'
        f'{T} style="max-width:640px;width:100%;font-family:{FONT};color:{C_NAVY};font-variant-numeric:tabular-nums;">'
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
