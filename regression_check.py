# -*- coding: utf-8 -*-
"""
回归对比工具 (Regression Harness)
---------------------------------
用途：验证修复版 htm_parser_fixed.py 是否会对存量单据引入新问题。

做法：
  1. 遍历 INPUT_DIR 下所有 .htm（默认 = 脚本目录/Input/BAK，
     因为主程序解析成功后会把 htm 从 Input 移动到 Input/BAK）
  2. 用修复版解析器重新解析
  3. 和 OUTPUT_DIR 下同名 .json（已知旧输出，基线）逐字段深比对
  4. 差异分类：
       - [FIX ] 项目(items)明细内的差异 —— 预期的修复
       - [WARN] 项目以外字段(编号/日期/客户编号/发货地址/联系人/公司...)差异
                —— 潜在回归，需人工确认
  5. 输出统计 + 明细，并导出 CSV

用法：
    # 方式A：零配置，自动使用 脚本目录下的 Input/BAK、Output、htm_parser_fixed.py
    python regression_check.py

    # 方式B：显式指定基准目录（可选）
    python regression_check.py --base "D:\\path\\to\\DeliveryNote"

    # 方式C：分别指定各路径（可选）
    python regression_check.py --input <htm目录> --output <基线json目录> --parser <解析器.py>

无需再手动改代码里的绝对路径。
"""

import os
import csv
import sys
import json
import argparse
import importlib.util
import logging


# ============ 路径自动定位（不再写死本机路径）============
def get_base_path() -> str:
    """
    返回脚本（或打包后 exe）所在目录，作为默认基准目录。
    - python regression_check.py  -> 脚本所在目录
    - 打包 exe                     -> exe 所在目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_paths():
    """解析命令行参数并结合默认值，给出最终使用的各路径。"""
    ap = argparse.ArgumentParser(description="Delivery Note 解析回归对比工具")
    ap.add_argument("--base", help="基准目录（默认=脚本所在目录）")
    ap.add_argument("--input", help="待重新解析的 .htm 目录（默认=<base>/Input/BAK，"
                                    "若不存在则回退 <base>/Input）")
    ap.add_argument("--output", help="基线 .json 目录（默认=<base>/Output）")
    ap.add_argument("--parser", help="修复版解析器路径（默认=<base>/htm_parser_fixed.py）")
    ap.add_argument("--csv", help="CSV 报告输出路径（默认=<base>/regression_report.csv）")
    args = ap.parse_args()

    base = os.path.abspath(args.base) if args.base else get_base_path()

    # INPUT：优先 Input/BAK（主程序把解析过的 htm 移到这里），没有则回退 Input
    if args.input:
        input_dir = os.path.abspath(args.input)
    else:
        bak = os.path.join(base, "Input", "BAK")
        input_dir = bak if os.path.isdir(bak) else os.path.join(base, "Input")

    output_dir = os.path.abspath(args.output) if args.output else os.path.join(base, "Output")
    parser_path = os.path.abspath(args.parser) if args.parser else os.path.join(base, "htm_parser_fixed.py")
    csv_out = os.path.abspath(args.csv) if args.csv else os.path.join(base, "regression_report.csv")

    return base, input_dir, output_dir, parser_path, csv_out
# =========================================================

TOP_FIELDS  = ["编号", "日期", "客户编号", "发货地址", "联系人", "联系电话", "标明"]
COMPANY_KEYS = ["name", "address", "phone", "fax"]
ITEM_FIELDS = ["项目行号", "零件号", "名字", "贵方零件号", "贵方订单号",
               "Our Order No.", "要求到货日期", "数量"]


def load_parser(path):
    logging.getLogger().addHandler(logging.NullHandler())
    spec = importlib.util.spec_from_file_location("fixed_parser", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compare(ref, new):
    """返回差异列表：(scope, key, old, new)"""
    diffs = []

    # 表头字段
    for k in TOP_FIELDS:
        if ref.get(k, "") != new.get(k, ""):
            diffs.append(("WARN", k, ref.get(k, ""), new.get(k, "")))

    # 公司字段
    rc = ref.get("公司", {}) or {}
    nc = new.get("公司", {}) or {}
    for k in COMPANY_KEYS:
        if rc.get(k, "") != nc.get(k, ""):
            diffs.append(("WARN", f"公司.{k}", rc.get(k, ""), nc.get(k, "")))

    # 项目数量
    ri, ni = ref.get("项目", []), new.get("项目", [])
    if len(ri) != len(ni):
        diffs.append(("WARN", "项目数量", len(ri), len(ni)))

    # 项目逐条
    for idx, (a, b) in enumerate(zip(ri, ni)):
        row = b.get("项目行号", f"#{idx}")
        for k in ITEM_FIELDS:
            if a.get(k, "") != b.get(k, ""):
                diffs.append(("FIX", f"行{row}.{k}", a.get(k, ""), b.get(k, "")))
    return diffs


def main():
    base, INPUT_DIR, OUTPUT_DIR, PARSER_PATH, CSV_OUT = resolve_paths()

    print("=" * 50)
    print(f"基准目录   : {base}")
    print(f"HTM 源目录 : {INPUT_DIR}")
    print(f"基线 JSON  : {OUTPUT_DIR}")
    print(f"解析器     : {PARSER_PATH}")
    print("=" * 50)

    # 基本存在性校验，给出友好提示而不是直接抛错
    for label, p in [("HTM 源目录", INPUT_DIR), ("基线 JSON 目录", OUTPUT_DIR),
                     ("解析器文件", PARSER_PATH)]:
        if not os.path.exists(p):
            print(f"[路径错误] {label} 不存在：{p}")
            print("           可用 --input / --output / --parser 显式指定，或用 --base 指向 DeliveryNote 根目录。")
            return

    parser_mod = load_parser(PARSER_PATH)
    cfg = parser_mod.load_config()

    rows = []
    n_files = n_ok = n_fix = n_warn = n_err = 0

    for fn in sorted(os.listdir(INPUT_DIR)):
        if not fn.lower().endswith(".htm"):
            continue
        n_files += 1
        htm_path = os.path.join(INPUT_DIR, fn)
        json_path = os.path.join(OUTPUT_DIR, fn.replace(".htm", ".json"))

        if not os.path.exists(json_path):
            print(f"[NO-BASE] {fn} (Output 里没有对应 .json，跳过比对)")
            rows.append([fn, "NO-BASE", "", "", ""])
            continue

        try:
            new = parser_mod.DeliveryNoteParser(htm_path, cfg).parse()
        except Exception as e:
            n_err += 1
            print(f"[ERROR ] {fn}: {e}")
            rows.append([fn, "ERROR", "", "", str(e)])
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            ref = json.load(f)

        diffs = compare(ref, new)
        if not diffs:
            n_ok += 1
            continue

        has_warn = any(d[0] == "WARN" for d in diffs)
        has_fix  = any(d[0] == "FIX" for d in diffs)
        if has_warn:
            n_warn += 1
        if has_fix:
            n_fix += 1

        print(f"\n=== {fn} ===")
        for scope, key, old, val in diffs:
            tag = "[FIX ]" if scope == "FIX" else "[WARN]"
            print(f"  {tag} {key}: 旧={old!r}  新={val!r}")
            rows.append([fn, scope, key, str(old), str(val)])

    # CSV
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "scope", "field", "old", "new"])
        w.writerows(rows)

    print("\n" + "=" * 50)
    print(f"总文件数        : {n_files}")
    print(f"完全一致        : {n_ok}")
    print(f"含项目修复(FIX) : {n_fix}")
    print(f"⚠️ 含表头变化(WARN): {n_warn}  <-- 重点人工确认这些")
    print(f"解析异常(ERROR) : {n_err}")
    print(f"明细已导出      : {CSV_OUT}")
    print("=" * 50)
    print("判定原则：")
    print("  - 只有 [FIX] 差异 → 属预期修复，安全。")
    print("  - 出现 [WARN] 差异 → 说明改动可能波及表头/公司字段，需逐一核对。")


if __name__ == "__main__":
    main()
