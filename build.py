#!/usr/bin/env python3
"""Google広告スクリプトが毎朝ドライブに書くCSV 2本から、index.html の `const AB = {...};` を実データで書き換える。
使い方: python3 build.py [--publish]   （毎朝 launchd com.yuki.mina-ads-ab-board が --publish 付きで実行 → 変更があれば push）
launchd からは /usr/bin/python3（3.9・ドライブを読める権限あり）で動かすので、3.9 で通る書き方にしておく。"""
import csv, json, re, subprocess, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.home() / "Library/CloudStorage/GoogleDrive-icchan417@gmail.com/マイドライブ/ads-export"
HTML = Path(__file__).with_name("index.html")
ADS = {"826392026602": "A", "826416311260": "B"}  # A=事実・安心 / B=感情・便益（広告グループ 206342583051）
START = "2026-09-30"
LB = {"BEST": "best", "GOOD": "good", "LOW": "low"}  # それ以外（LEARNING / PENDING / NOT_APPLICABLE）は学習中
WD = "月火水木金土日"


def read_rows(path):
    # ドライブの同期中は launchd から開くと EDEADLK(11) になる（10/1, 10/2 5:30、10/4 5:30+9:30 実測）。
    # 300秒でも抜けない日があり2回連続のscheduled runが両方失敗したので900秒に拡大
    for i in range(30):
        try:
            with open(path, newline="") as f:
                return list(csv.DictReader(f))
        except OSError as e:
            if e.errno != 11 or i == 29:
                raise
            time.sleep(30)


def load(latest):
    by_day = read_rows(latest / "ad_by_day.csv")
    assets = [r for r in read_rows(latest / "asset_by_ad.csv") if r["ad_group_ad_asset_view.field_type"] == "HEADLINE"]
    return by_day, assets


def build(by_day, assets, old, today):
    yesterday = (today - timedelta(days=1)).isoformat()
    days, d = [], date.fromisoformat(START)
    while d.isoformat() <= max(START, yesterday):
        days.append({"date": d.isoformat(), "w": WD[d.weekday()],
                     "A": {"imp": 0, "clk": 0, "cost": 0, "bc": 0}, "B": {"imp": 0, "clk": 0, "cost": 0, "bc": 0}})
        d += timedelta(days=1)
    idx = {x["date"]: x for x in days}
    for r in by_day:
        s, day = ADS.get(r["ad_group_ad.ad.id"]), idx.get(r["segments.date"])
        if not s or not day:
            continue
        day[s]["imp"] += int(r["metrics.impressions"])
        day[s]["clk"] += int(r["metrics.clicks"])
        day[s]["cost"] += round(int(r["metrics.cost_micros"]) / 1e6)
    ja = {a["t"]: a.get("ja", "") for s in "AB" for a in old.get("assets", {}).get(s, [])}
    out = {"A": [], "B": []}
    for r in assets:
        s = ADS.get(r["ad_group_ad.ad.id"])
        if not s:
            continue
        t, lb = r["asset.text_asset.text"], LB.get(r.get("ad_group_ad_asset_view.performance_label", ""), "learn")
        imp, clk = int(r["metrics.impressions"]), int(r["metrics.clicks"])
        out[s].append({"t": t, "ja": ja.get(t, ""), "lb": lb, "imp": imp,
                       "clk": clk, "ctr": clk / imp if imp else None})  # 学習中も出す（判定に使わないだけ）
    return {"start": START, "min": old.get("min", 100), "budget": old.get("budget", 1300), "real": True,
            "days": days, "assets": out}


def main():
    folders = sorted(p for p in ROOT.glob("20*") if p.is_dir())
    if not folders:
        sys.exit(f"CSVのフォルダがない: {ROOT}")
    html = HTML.read_text()
    m = re.search(r"^const AB = (\{.*\});$", html, re.M)
    ab = build(*load(folders[-1]), json.loads(m.group(1)), datetime.now(timezone(timedelta(hours=9))).date())
    HTML.write_text(html[:m.start(1)] + json.dumps(ab, ensure_ascii=False) + html[m.end(1):])
    print(f"{folders[-1].name}: {len(ab['days'])}日分 / 見出し A{len(ab['assets']['A'])} B{len(ab['assets']['B'])}")
    if "--publish" in sys.argv:
        git = lambda *a: subprocess.run(["/usr/bin/git", "-C", str(HTML.parent), *a], check=True)
        if subprocess.run(["/usr/bin/git", "-C", str(HTML.parent), "diff", "--quiet", "index.html"]).returncode:
            git("commit", "-q", "-m", f"実データ更新 {folders[-1].name}", "index.html")
            git("push", "-q")
            print("pushed")
        HTML.with_name(".last-success").write_text(datetime.now().isoformat())


if __name__ == "__main__":
    main()
