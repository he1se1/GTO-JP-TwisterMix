import json
import os
import re
from pathlib import Path
from datetime import datetime

# 実行ディレクトリを基準にする
MANUAL_DIR = 'manual-repo'
MT_DIR = 'mt-repo'
OUTPUT_DIR = 'output'

def contains_japanese(text):
    if not text: return False
    # ひらがな、カタカナ、漢字が含まれているか
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', str(text)))

def safe_load_json(path):
    if not os.path.exists(path): return {}
    try:
        # BOM付きUTF-8への対応
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {path} - {e}")
        return {}

# 1. ファイルの収集
# key: lowercase_rel_path (normalized), value: { 'targets': set(filenames), 'manual': [paths], 'mt': [paths] }
file_groups = {}

def collect_files(base_dir, label):
    if not os.path.exists(base_dir):
        print(f"Notice: {base_dir} not found.")
        return
    for p in Path(base_dir).rglob('*.json'):
        # ja_jp.json, ja_JP.json, ja_01.json 等を対象にする
        if p.name.lower().startswith('ja_'):
            try:
                rel_path = p.relative_to(base_dir)
            except ValueError:
                continue
                
            lower_rel_path = str(rel_path).replace('\\', '/').lower()
            
            # ターゲット名を ja_jp.json に正規化したパスをキーにする
            # (例: assets/modid/lang/ja_jp.json)
            target_key = re.sub(r'ja_[a-z0-9_]+\.json$', 'ja_jp.json', lower_rel_path)
            
            if target_key not in file_groups:
                file_groups[target_key] = {'targets': set(), 'manual': [], 'mt': []}
            
            # 元のファイル名を記録（後でこの名前で出力するため）
            file_groups[target_key]['targets'].add(p.name)
            file_groups[target_key][label].append(p)

print("Searching for language files...")
collect_files(MANUAL_DIR, 'manual')
collect_files(MT_DIR, 'mt')

# 2. マージ実行
merged_count = 0
for rel_path, data in file_groups.items():
    m_data = {}
    for p in data['manual']:
        m_data.update(safe_load_json(p))
    
    mt_data = {}
    for p in data['mt']:
        mt_data.update(safe_load_json(p))
    
    merged_data = {}
    all_keys = set(m_data.keys()) | set(mt_data.keys())
    
    count_manual_hit = 0
    for key in all_keys:
        m_val = m_data.get(key)
        mt_val = mt_data.get(key)
        
        # 判定ロジック:
        # 1. 手動側に日本語があれば優先採用
        # 2. 手動側が英語等でも、機械翻訳(Gemini)側が日本語なら「翻訳」として機械翻訳を採用
        # 3. どちらも日本語でない場合（記号やフォーマット文字列のみ）は手動側を優先（マスターとして尊重）
        
        if m_val and contains_japanese(m_val):
            merged_data[key] = m_val
            count_manual_hit += 1
        elif mt_val and contains_japanese(mt_val):
            merged_data[key] = mt_val
        else:
            merged_data[key] = m_val or mt_val

    # 3. 書き出し
    # 元のリポジトリにあった全てのファイル名バリエーションで出力する
    # これにより Mod が期待する ja_JP.json 等の欠落を防ぐ
    for filename in data['targets']:
        out_rel_path = re.sub(r'ja_jp\.json$', filename, rel_path)
        out_path = os.path.join(OUTPUT_DIR, out_rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, sort_keys=True, indent=4)
    
    merged_count += 1
    if count_manual_hit > 0:
        print(f"Merged {rel_path}: Using {count_manual_hit} manual translations.")
    else:
        print(f"Merged {rel_path}: MT only or manual placeholder used.")

# 4. pack.mcmeta のコピーまたは生成
# mt-repo にあればそれをベースにする
mcmeta_src = os.path.join(MT_DIR, 'pack.mcmeta')
mcmeta_out = os.path.join(OUTPUT_DIR, 'pack.mcmeta')
if os.path.exists(mcmeta_src):
    mcmeta_data = safe_load_json(mcmeta_src)
    # 説明文を更新（オプション）
    if 'pack' in mcmeta_data:
        mcmeta_data['pack']['description'] = f"GTO-JP Mixed Pack (Manual + Gemini) - {datetime.now().strftime('%Y-%m-%d')}"
    with open(mcmeta_out, 'w', encoding='utf-8') as f:
        json.dump(mcmeta_data, f, ensure_ascii=False, indent=4)
elif not os.path.exists(mcmeta_out):
    with open(mcmeta_out, 'w', encoding='utf-8') as f:
        json.dump({
            "pack": {
                "pack_format": 15,
                "description": f"GTO-JP Mixed Pack - {datetime.now().strftime('%Y-%m-%d')}"
            }
        }, f, ensure_ascii=False, indent=4)

print(f"\nProcessing complete. {merged_count} unique lang paths processed.")