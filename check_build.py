#!/usr/bin/env python3
"""com.yuki.mina-ads-ab-board の build.py に対する最小runnable check（B31_38・新規追加）。

これまでの死活監視（check_B31_16.py）はlaunchdのLastExitStatusと
ログに"pushed"の文字列があるかしか見ておらず、2026-10-17に実際に起きた
「GDrive EDEADLKで取得失敗→exit 0のまま 見出しA0 B0 を本番へpush」という
“中身が空でも正常終了に見える”不調を検出できなかった（B31_16で記録済み・未修理）。

今回はbuild.py本体には一切手を入れず（根本原因の修理はしない指示のため）、
純粋関数 build() の集計ロジックに初めてunitレベルのassertを与える。
通常ケースの検証に加え、既知の空データケース（由来: 2026-10-17の実害）が
現状どう振る舞うかもそのまま記録する（ガードを追加するものではない）。

実行: python3 -I ~/mina-ads-ab-board-01/check_build.py
"""
import importlib.util
import os
from datetime import date

MODULE_PATH = os.path.join(os.path.dirname(__file__), "build.py")
spec = importlib.util.spec_from_file_location("mina_ads_build", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)  # build.py はimport時にファイルI/Oをしない（main()はガード済み）


def row(ad_id, d, imp, clk, cost_micros):
    return {
        "ad_group_ad.ad.id": ad_id,
        "segments.date": d,
        "metrics.impressions": str(imp),
        "metrics.clicks": str(clk),
        "metrics.cost_micros": str(cost_micros),
    }


def asset_row(ad_id, text, label, imp, clk):
    return {
        "ad_group_ad.ad.id": ad_id,
        "asset.text_asset.text": text,
        "ad_group_ad_asset_view.performance_label": label,
        "metrics.impressions": str(imp),
        "metrics.clicks": str(clk),
    }


def test_date_range_and_weekday():
    out = m.build([], [], {}, date(2026, 10, 3))
    days = out["days"]
    assert [d["date"] for d in days] == ["2026-09-30", "2026-10-01", "2026-10-02"], days
    # START=2026-09-30は水曜
    assert days[0]["w"] == "水", days[0]["w"]
    assert out["start"] == "2026-09-30"


def test_aggregation_by_day():
    by_day = [
        row("826392026602", "2026-09-30", 100, 10, 5_000_000),   # A
        row("826392026602", "2026-09-30", 50, 5, 1_000_000),     # A同日2行目→加算されるはず
        row("826416311260", "2026-09-30", 200, 20, 8_000_000),   # B
        row("999999999999", "2026-09-30", 999, 99, 999_000_000),  # 未知のad_id→無視
        row("826392026602", "2026-08-01", 1, 1, 1_000_000),      # 範囲外日付→無視
    ]
    out = m.build(by_day, [], {}, date(2026, 10, 1))
    d0 = out["days"][0]
    assert d0["date"] == "2026-09-30"
    assert d0["A"] == {"imp": 150, "clk": 15, "cost": 6, "bc": 0}, d0["A"]
    assert d0["B"] == {"imp": 200, "clk": 20, "cost": 8, "bc": 0}, d0["B"]


def test_asset_labels_and_ctr_and_ja_carry_over():
    assets = [
        asset_row("826392026602", "見出しA1", "BEST", 100, 10),
        asset_row("826392026602", "見出しA2", "NOT_APPLICABLE", 0, 0),  # imp=0 → ctr None
        asset_row("826416311260", "見出しB1", "GOOD", 50, 5),
    ]
    old = {"assets": {"A": [{"t": "見出しA1", "ja": "前回つけた日本語メモ"}]}}
    out = m.build([], assets, old, date(2026, 10, 1))
    a1 = next(a for a in out["assets"]["A"] if a["t"] == "見出しA1")
    assert a1["lb"] == "best", a1
    assert a1["ctr"] == 10 / 100, a1
    assert a1["ja"] == "前回つけた日本語メモ", a1  # old側のjaが引き継がれる
    a2 = next(a for a in out["assets"]["A"] if a["t"] == "見出しA2")
    assert a2["lb"] == "learn", a2  # LBマップ外のラベルはlearnに正規化
    assert a2["ctr"] is None, a2  # imp=0時はZeroDivisionErrorを起こさずNone
    b1 = out["assets"]["B"][0]
    assert b1["lb"] == "good", b1


def test_known_gap_empty_assets_yields_empty_output_no_guard():
    """2026-10-17の実害の再現（記録のみ・ガードは追加しない）。
    stage_ads_export.pyがGDrive EDEADLKで失敗し、assets/by_dayが実質空のまま
    read_rows()が通ってしまった場合、build()はエラーを出さずそのまま
    見出し0件・集計0件の“空だが正常に見える”結果を返す。
    = 呼び出し側（daily_check.py等）が空チェックを入れない限り、この空結果が
      そのままindex.htmlにpushされてしまう設計上のギャップが現在も残っている。
    """
    out = m.build([], [], {}, date(2026, 10, 18))
    assert out["assets"]["A"] == [] and out["assets"]["B"] == []
    assert all(day["A"]["imp"] == 0 for day in out["days"])


def main():
    test_date_range_and_weekday()
    test_aggregation_by_day()
    test_asset_labels_and_ctr_and_ja_carry_over()
    test_known_gap_empty_assets_yields_empty_output_no_guard()
    print("OK: build() 日付範囲/集計/ラベル付け/ja引継ぎ 計4テストPASS"
          "（空データ時にA0 B0を無警告で返す既知ギャップも再現確認・ガード追加なし）")


if __name__ == "__main__":
    main()
