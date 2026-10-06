#!/usr/bin/env python3
"""观察池日报：纯固定公式扫描（与 indicators/ 下两个 Pine 指标同一套公式），不涉及任何 AI。

用法：
    python scanner/scan.py               # 扫描 + 写 scan.md + （若配置了环境变量）发邮件
    python scanner/scan.py --no-email    # 只写文件

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
            df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False, actions=False)
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


def build_html(results: list[Result], data_date: str, gen_time: str) -> str:
    e = html.escape
    UP, DOWN, FLAT = "#d93025", "#188038", "#5f6368"  # 红涨绿跌
    color = {"up": UP, "down": DOWN, "flat": FLAT}

    def chg_color(x):
        return FLAT if nan(x) or x == 0 else (UP if x > 0 else DOWN)

    td = "padding:6px 8px;border-bottom:1px solid #eee;white-space:nowrap;font-size:13px;"
    th = "padding:6px 8px;border-bottom:2px solid #ddd;background:#f6f8fa;text-align:left;white-space:nowrap;font-size:12px;color:#555;"
    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>',
        '<body style="margin:0;padding:0;background:#f4f5f7;">',
        '<div style="max-width:720px;margin:0 auto;padding:12px;font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',Helvetica,Arial,sans-serif;color:#202124;">',
        f'<h2 style="margin:4px 0 2px;font-size:20px;">观察池日报 {e(data_date)}</h2>',
        f'<div style="font-size:12px;color:#777;margin-bottom:12px;">数据日期 {e(data_date)} · 生成于 {e(gen_time)}（北京时间） · Yahoo Finance 日线 · 固定公式</div>',
    ]
    # 今日变化
    parts.append('<div style="background:#fff8e1;border-left:4px solid #f9ab00;border-radius:6px;padding:10px 12px;margin-bottom:14px;">')
    parts.append('<div style="font-weight:600;font-size:15px;margin-bottom:6px;">今日变化</div>')
    changed = [r for r in results if r.ok and r.changes]
    if changed:
        for r in changed:
            items = "　".join(f'<span style="color:{color[k]};">{e(t)}</span>' for k, t in r.changes)
            parts.append(f'<div style="font-size:14px;line-height:1.7;"><b>{e(r.symbol)}</b>：{items}</div>')
    else:
        parts.append('<div style="font-size:14px;color:#555;">今日无新信号</div>')
    missing = [r for r in results if not r.ok]
    if missing:
        parts.append('<div style="font-size:13px;color:#b00020;margin-top:6px;">数据缺失：' +
                     e("、".join(r.symbol for r in missing)) + "</div>")
    parts.append("</div>")

    # 总览表
    parts.append('<div style="background:#fff;border-radius:6px;padding:8px;margin-bottom:14px;">')
    parts.append('<div style="font-weight:600;font-size:15px;margin:2px 4px 6px;">总览</div>')
    parts.append('<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">')
    parts.append('<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">')
    parts.append("<tr>" + "".join(f'<th style="{th}">{h}</th>' for h in ["代码", "收盘", "涨跌", "均线", "结构", "相对", "风险收益比"]) + "</tr>")
    for r in results:
        if not r.ok:
            parts.append(f'<tr><td style="{td}font-weight:600;">{e(r.symbol)}</td><td colspan="6" style="{td}color:#b00020;">数据缺失</td></tr>')
            continue
        v = r.v
        bg = "background:#fffbea;" if r.changes else ""
        sc = UP if v["struct_txt"] == "突破近高" else DOWN if v["struct_txt"] == "跌破近低" else FLAT
        ac = UP if v["align_txt"] == "多头排列" else DOWN if v["align_txt"] == "空头排列" else FLAT
        rc = UP if v["rs_txt"] == "偏强" else DOWN if v["rs_txt"] == "偏弱" else FLAT
        parts.append(
            f'<tr style="{bg}"><td style="{td}font-weight:600;">{e(r.symbol)}</td>'
            f'<td style="{td}">{fp(v["close"])}</td>'
            f'<td style="{td}color:{chg_color(v["chg"])};">{fpct(v["chg"], 2)}</td>'
            f'<td style="{td}color:{ac};">{e(v["align_txt"])}</td>'
            f'<td style="{td}color:{sc};">{e(v["struct_txt"])}</td>'
            f'<td style="{td}color:{rc};">{e(v["rs_txt"])}</td>'
            f'<td style="{td}">{e(rr_txt(v["rr"]))}</td></tr>')
    parts.append("</table></div></div>")

    # 每只明细卡片
    kv_k = "padding:4px 6px;color:#666;font-size:13px;white-space:nowrap;vertical-align:top;width:84px;"
    kv_v = "padding:4px 6px;font-size:13px;"
    for r in results:
        if not r.ok:
            continue
        v = r.v
        border = "border:2px solid #f9ab00;" if r.changes else "border:1px solid #e3e3e3;"
        parts.append(f'<div style="background:#fff;{border}border-radius:6px;padding:10px;margin-bottom:10px;">')
        parts.append(
            f'<div style="font-size:16px;font-weight:600;">{e(r.symbol)} '
            f'<span style="font-weight:400;">{fp(v["close"])}</span> '
            f'<span style="color:{chg_color(v["chg"])};font-size:14px;">{fpct(v["chg"], 2)}</span>'
            f'<span style="float:right;font-size:12px;color:#888;font-weight:400;">{e(r.date)}</span></div>')
        if r.changes:
            parts.append('<div style="font-size:13px;margin:4px 0;">' + "　".join(
                f'<span style="color:{color[k]};">● {e(t)}</span>' for k, t in r.changes) + "</div>")
        kvs = [
            ("均线", f"{v['pos_txt']} · {v['align_txt']}"),
            ("结构", v["struct_txt"]),
            ("量能", vol_txt(v["vol_ratio"]) + " 均量"),
            ("相对", f"{v['rs_txt']} vs {r.bench}"),
            ("近低/近高", f"{fp(v['ll'])} / {fp(v['hh'])}"),
            ("ATR14", fp(v["atr"])),
            ("离MA20", dist_txt(v["d20p"], v["d20a"])),
            ("离MA50", dist_txt(v["d50p"], v["d50a"])),
            ("一年位置", pos52_txt(v["pos52"])),
            ("涨/跌量比", ud_txt(v["ud"])),
            ("ATR分位", atr_rank_txt(v["atr_rank"])),
            ("止损", stop_txt(v)),
            ("目标", target_txt(v)),
            ("风险收益比", rr_txt(v["rr"])),
        ]
        if r.notes:
            kvs.append(("备注", "，".join(r.notes)))
        parts.append('<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;margin-top:4px;">')
        for k, val in kvs:
            parts.append(f'<tr><td style="{kv_k}">{e(k)}</td><td style="{kv_v}">{e(val)}</td></tr>')
        parts.append("</table></div>")

    parts.append('<div style="font-size:12px;color:#888;line-height:1.6;margin-top:12px;">'
                 "红涨绿跌。止损 = max(20 根最低, 收盘 − 2×ATR)；目标 = 20 根最高（已突破则按 2R）。"
                 "<br><b>不构成投资建议。</b>仅为固定公式的机械计算结果，数据可能有延迟或错误。</div>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


# =====================================================================
# 观察池 / 邮件 / 主流程
# =====================================================================
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

    data_date = max(r.date for r in ok)
    gen_time = datetime.now(BJ).strftime("%Y-%m-%d %H:%M")
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
