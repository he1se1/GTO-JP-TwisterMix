import json
import os
import re
from pathlib import Path
from datetime import datetime

MANUAL_DIR = 'manual-repo'
MT_DIR = 'mt-repo'
OUTPUT_DIR = 'output'

def contains_japanese(text):
    if not text: return False
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', str(text)))

def safe_load_json(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {path} - {e}")
        return {}

# 1. 両方のリポジトリから ja_jp.json のパスをすべて抽出
all_rel_paths = set()
for repo in [MANUAL_DIR, MT_DIR]:
    for p in Path(repo).rglob('ja_jp.json'):
        # 各リポジトリのルートからの相対パスを取得
        all_rel_paths.add(p.relative_to(repo))

# 2. 全パスに対してマージ処理
for rel_path in all_rel_paths:
    manual_path = os.path.join(MANUAL_DIR, rel_path)
    mt_path = os.path.join(MT_DIR, rel_path)
    out_path = os.path.join(OUTPUT_DIR, rel_path)

    m_data = safe_load_json(manual_path)
    mt_data = safe_load_json(mt_path)

    merged_data = {}
    # 両方のJSONにあるキーをすべて合わせる
    all_keys = set(m_data.keys()) | set(mt_data.keys())
    count_manual = 0

    for key in all_keys:
        m_val = m_data.get(key)
        mt_val = mt_data.get(key)

        # 判定ロジック:
        # 手動側にキーがあり、かつ日本語が含まれていれば採用
        if m_val and contains_japanese(m_val):
            merged_data[key] = m_val
            count_manual += 1
        # それ以外（手動側が英語、または手動側にキーがない）なら機械翻訳側を採用
        elif mt_val:
            merged_data[key] = mt_val
        # どちらにも値があるがどちらも日本語でない場合などのフォールバック
        else:
            merged_data[key] = m_val or mt_val

    # 保存先ディレクトリを作成して書き出し
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=4)
    if count_manual > 0:
        print(f"ファイル{rel_path}で{count_manual}件の手動翻訳を採用")

# 3. pack.mcmeta の生成
mcmeta_path = os.path.join(OUTPUT_DIR, 'pack.mcmeta')
with open(mcmeta_path, 'w', encoding='utf-8') as f:
    json.dump({
        "pack": {
            "pack_format": 15,
            "description": f"GregTech Odyssey日本語化リソースパック Twister716氏による訳の不足分に機械翻訳を統合 ({datetime.now().strftime('%Y-%m-%d')})"
        }
    }, f, indent=4)

print(f"Processing complete. {len(all_rel_paths)} files merged.")