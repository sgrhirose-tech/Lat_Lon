#!/usr/bin/env python3
"""
update_notes.py — Claude API を使って既存スポットの notes を一括再生成する

使い方:
  python3 tools/update_notes.py --pref kanagawa chiba tokyo   # 全件更新
  python3 tools/update_notes.py --pref kanagawa --dry-run     # プレビューのみ
  python3 tools/update_notes.py --slug akiya                  # 1件テスト

環境変数:
  ANTHROPIC_API_KEY  — Claude API キー（必須）
"""

import argparse
import json
import os
import time
from pathlib import Path

import anthropic

SPOTS_DIR = Path(__file__).parent.parent / "spots"

# 地形分類の日本語ラベル
PRIMARY_TYPE_JA = {
    "sand_beach":        "砂浜",
    "rocky_shore":       "磯・岩場",
    "fishing_facility":  "漁港・釣り施設",
    "breakwater":        "堤防・防波堤",
    "river_mouth":       "河口",
    "reclaimed_land":    "埋立地・護岸",
    "bay_beach":         "内湾砂浜",
    "unknown":           "不明",
}

SEABED_TYPE_JA = {
    "sand":  "砂",
    "rock":  "岩・石",
    "mixed": "混合（砂・岩）",
    "mud":   "泥",
}


def build_prompt(spot: dict) -> str:
    name       = spot.get("name", "")
    info       = spot.get("info", {})
    area       = spot.get("area", {})
    phys       = spot.get("physical_features", {})
    derived    = spot.get("derived_features", {})
    cls        = spot.get("classification", {})

    prefecture  = area.get("prefecture", "")
    area_name   = area.get("area_name", "")
    city        = area.get("city", "")
    ptype_raw   = cls.get("primary_type", "unknown")
    ptype_ja    = PRIMARY_TYPE_JA.get(ptype_raw, ptype_raw)
    seabed_raw  = phys.get("seabed_type", "")
    seabed_ja   = SEABED_TYPE_JA.get(seabed_raw, seabed_raw)
    seabed_sum  = derived.get("seabed_summary", "")
    kisugo      = derived.get("bottom_kisugo_score", "")
    depth_dist  = phys.get("nearest_20m_contour_distance_m", "")
    surfer      = phys.get("surfer_spot", False)
    current     = info.get("notes", "")

    depth_str = f"{depth_dist:.0f}m" if isinstance(depth_dist, (int, float)) else ""

    return f"""\
あなたは釣り場ガイドの編集者です。
以下のスポット情報をもとに、釣り人向けの紹介文（notes）を日本語2文以内で書いてください。

【条件】
- 釣れる魚種を季節感を含めてできるだけ具体的に挙げる
- 釣り方・ポイントの特徴を加える
- 「です・ます」調不要、簡潔に
- 50文字以内が理想

【スポット情報】
名称: {name}
都道府県: {prefecture}
エリア: {area_name}
市区: {city}
地形分類: {ptype_ja}
海底: {seabed_ja}（{seabed_sum}）
水深20m線まで: {depth_str}
サーフスポット: {"あり" if surfer else "なし"}
キス適性スコア: {kisugo}/100
既存notes: {current}

【出力】
notesのテキストのみ（1〜2文、日本語）。前置きや説明は不要。"""


def generate_notes(client: anthropic.Anthropic, spot: dict) -> str:
    prompt = build_prompt(spot)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def load_spots(pref_slugs: list[str], slugs: list[str]) -> list[Path]:
    paths = sorted(SPOTS_DIR.glob("*.json"))
    result = []
    for p in paths:
        if p.name.startswith("_"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        if slugs:
            if data.get("slug") in slugs:
                result.append(p)
        elif pref_slugs:
            if data.get("area", {}).get("pref_slug") in pref_slugs:
                result.append(p)
    return result


def main():
    parser = argparse.ArgumentParser(description="Claude API で spots の notes を再生成")
    parser.add_argument("--pref",    nargs="+", default=[],
                        help="都道府県スラグ (kanagawa / chiba / tokyo / shizuoka ...)")
    parser.add_argument("--slug",    nargs="+", default=[],
                        help="スポットスラグ（個別指定）")
    parser.add_argument("--dry-run", action="store_true",
                        help="生成結果を表示するだけで書き込まない")
    parser.add_argument("--sleep",   type=float, default=0.5,
                        help="API呼び出し間のスリープ秒数（デフォルト 0.5）")
    args = parser.parse_args()

    if not args.pref and not args.slug:
        parser.error("--pref または --slug を指定してください")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("エラー: 環境変数 ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    paths = load_spots(args.pref, args.slug)
    if not paths:
        print("対象スポットが見つかりませんでした。")
        return

    print(f"対象: {len(paths)} 件  dry-run={'ON' if args.dry_run else 'OFF'}")
    print()

    for i, path in enumerate(paths, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        name    = data.get("name", path.stem)
        old     = data.get("info", {}).get("notes", "")

        print(f"[{i}/{len(paths)}] {name}")
        print(f"  旧: {old}")

        try:
            new_notes = generate_notes(client, data)
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(args.sleep)
            continue

        print(f"  新: {new_notes}")

        if not args.dry_run:
            data["info"]["notes"] = new_notes
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"  → 書き込み完了")

        print()
        time.sleep(args.sleep)

    print("完了。")


if __name__ == "__main__":
    main()
