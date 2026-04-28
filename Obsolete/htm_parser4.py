# -*- coding: utf-8 -*-
# ==========================================
# Delivery Note HTM -> JSON Parser (V3.0)
# Block-based, position-first, multi-page safe
# ==========================================

import os
import re
import json
import sys
from bs4 import BeautifulSoup
from typing import List, Dict
import yaml

def load_config(config_path: str = "config.yaml") -> dict:
    default_config = {
        "paths": {
            "input_dir": "Docs",
            "output_dir": "Output"
        },
        "keywords": {
            "remark_start": ["备注"],
            "remark_end": ["项目零件号", "项目", "Pos."],
            "shipping": {
                "contact": ["联系人", "收货人"],
                "address": ["发货地址", "收货地址", "地址"],
                "phone": ["电话", "联系电话"]
            },
            "mark": ["标明"]
        }
    }

    if not os.path.exists(config_path):
        return default_config

    with open(config_path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}

    # 简单 merge（浅合并，已够用）
    for k, v in default_config.items():
        if k not in user_cfg:
            user_cfg[k] = v

    return user_cfg

# ----------------------------
# 基础正则
# ----------------------------

NUMBER_KEYS = ["编号", "Number"]
DATE_KEYS = ["日期", "Date"]
CUSTOMER_KEYS = ["客户编号", "Customer No."]

#ITEM_LINE_RE = re.compile(r"^(\d{3})\s+([A-Z0-9]{6,})\s+(.*)")
ITEM_LINE_RE = re.compile(r"^\s*(\d{3})\s+([A-Z0-9]{6,})\s+(.*)")
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
PHONE_MOBILE_RE = re.compile(r"\b1\d{10}\b")
PHONE_LANDLINE_RE = re.compile(r"\b(?:\+86\s?)?0\d{2,3}[-\s]?\d{7,8}\b")


# ----------------------------
# Parser 主类
# ----------------------------

class DeliveryNoteParser:

    def __init__(self, htm_path: str, config: dict):
        self.htm_path = htm_path
        self.config = config
        self.soup = None
        self.lines: List[str] = []

    # ----------------------------
    # 主入口
    # ----------------------------

    def parse(self) -> Dict:
        self._load()
        self._normalize_lines()

        shipping_info = self._extract_shipping_info()
        remark_block = self._extract_remark_block()

        result = {
            "file_name": os.path.basename(self.htm_path),
            "编号": self._extract_number(),
            "日期": self._extract_date(),
            "客户编号": self._extract_customer_no(),
            "发货地址": shipping_info["发货地址"],
            "联系人": shipping_info["联系人"],
            "联系电话": shipping_info["联系电话"],
            "标明": self._extract_mark_from_remark(remark_block),
            "项目": self._parse_items()
        }
        return result

    # ----------------------------
    # 预处理
    # ----------------------------

    def _load(self):
        with open(self.htm_path, "r", encoding="utf-8", errors="ignore") as f:
            self.soup = BeautifulSoup(f, "html.parser")

    def _normalize_lines(self):
        raw = self.soup.get_text(separator="\n")
        
        # ✅ 1. 保留原始行（用于项目区解析）
        self.raw_lines = [
            line.rstrip("\n")
            for line in raw.split("\n")
            if line.strip()
        ]

        # ✅ 2. 规范化行（用于备注 / 地址 / 普通字段）
        self.lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in raw.split("\n")
            if line.strip()
        ]

    #-----------------------------
    # 清洗字符串
    #-----------------------------
    def _clean_text(self, text: str) -> str:
        """
        清洗 HTML 文本残留：
        - &nbsp; / \xa0 → 普通空格
        - 多空格压缩
        - 首尾空格
        """
        if not text:
            return ""

        # 把 nbsp 转成普通空格
        text = text.replace("\xa0", " ").replace("&nbsp;", " ")

        # 压缩多余空格
        text = re.sub(r"\s+", " ", text)

        return text.strip()
    
    # ----------------------------
    # 基础字段
    # ----------------------------

    def _search_by_anchor(self, keys, pattern):
        for i, line in enumerate(self.lines):
            if any(k in line for k in keys):
                for j in range(i, min(i + 3, len(self.lines))):
                    m = re.search(pattern, self.lines[j])
                    if m:
                        return m.group()
        return ""

    def _extract_number(self):
        return self._search_by_anchor(NUMBER_KEYS, r"\b\d{8}\b")

    def _extract_date(self):
        return self._search_by_anchor(DATE_KEYS, DATE_RE)

    def _extract_customer_no(self):
        return self._search_by_anchor(CUSTOMER_KEYS, r"\b[A-Z0-9]{4,}\b")

    def _clean_address_text(self, text: str) -> str:
        """
        根据 config.yaml 清洗地址文本：
        - 去引号
        - 去前缀标签
        """
        if not text:
            return ""

        cfg = self.config.get("address_clean", {})

        # 1️⃣ 去引号
        if cfg.get("strip_quotes", True):
            text = text.strip().strip('"').strip("'")

        # 2️⃣ 去地址前缀
        prefixes = cfg.get("prefixes", [])
        for p in prefixes:
            if text.startswith(p):
                text = text[len(p):]
                break  # ⚠️ 命中一个就停，防止误切

        return text.strip()
    
    
    # ----------------------------
    # 备注区块（核心）
    # ----------------------------

    def _extract_remark_block(self) -> List[str]:
        """
        提取“备注”到“项目零件号 / Pos.” 之间的所有行
        """
        cfg = self.config["keywords"]
        block = []
        in_block = False

        
        for line in self.lines:
            if any(line.startswith(k) for k in cfg["remark_start"]):
                in_block = True
                continue

            if in_block and any(line.startswith(k) for k in cfg["remark_end"]):
                break

            if in_block:
                block.append(line)

        return block

    def _extract_mark_from_remark(self, block: List[str]) -> str:
        """
        从备注区块中提取“标明”
        """
        
        mark_keys = self.config["keywords"]["mark"]

        for line in block:
            for k in mark_keys:
                if f"{k}：" in line:
                    return line.split(f"{k}：", 1)[1].strip()

        return ""

    # ----------------------------
    # 收货信息（备注 / 单行 双兜底）
    # ----------------------------

    def extract_contact_from_single_line(self, raw: str) -> str:
        """
        从“地址 + 联系人”字符串中提取联系人
        规则：
        - 按空格分段
        - 取最后一段
        - 提取前 2～3 个中文字符
        """
        parts = raw.strip().split()
        if not parts:
            return ""

        candidate = parts[-1]

        # 只保留中文字符
        chinese_chars = "".join(re.findall(r"[\u4e00-\u9fa5]", candidate))

        if len(chinese_chars) >= 3:
            return chinese_chars[:3]
        elif len(chinese_chars) == 2:
            return chinese_chars
        else:
            return ""
    
    def _extract_shipping_info(self) -> Dict:
        cfg = self.config["keywords"]["shipping"]

        result = {
            "发货地址": "",
            "联系人": "",
            "联系电话": ""
        }

        block = self._extract_remark_block()

        # ----------------------------------
        # Step 1️⃣ 判断是否结构化多行
        # ----------------------------------
        has_structured_keys = any(
            any(k in line for k in cfg["contact"] + cfg["phone"])
            for line in block
        )

        # ========= 逻辑 1：结构化多行 =========
        if has_structured_keys:
            for line in block:
                # 联系人
                if any(k in line for k in cfg["contact"]):
                    result["联系人"] = line.split("：", 1)[-1].strip()

                # 电话
                elif any(k in line for k in cfg["phone"]):
                    m = PHONE_MOBILE_RE.search(line) or PHONE_LANDLINE_RE.search(line)
                    if m:
                        result["联系电话"] = m.group()

                # 地址（注意：这里不 return，还要做二次清洗）
                elif any(k in line for k in cfg["address"]):
                    addr = line.split("：", 1)[-1].strip()

                    # 👉 地址行中可能包含电话
                    m_phone = PHONE_MOBILE_RE.search(addr) or PHONE_LANDLINE_RE.search(addr)
                    if m_phone:
                        result["联系电话"] = m_phone.group()
                        addr = addr[:m_phone.start()]
                    """
                    # 👉 地址行中可能包含联系人（2-3 个中文）
                    m_contact = re.search(r"([\u4e00-\u9fa5]{2,3})\s*$", addr)
                    if m_contact and not result["联系人"]:
                        result["联系人"] = m_contact.group(1)
                        addr = addr[:m_contact.start()]
                    """
                    result["发货地址"] = self._clean_address_text(addr)

            return result

        # ========= 逻辑 2：单行自由文本 =========
        for line in block:
            m_phone = PHONE_MOBILE_RE.search(line) or PHONE_LANDLINE_RE.search(line)
            if not m_phone:
                continue

            result["联系电话"] = m_phone.group()
            raw = line[:m_phone.start()]

            # 联系人
            if " " in raw:
                m_contact = self.extract_contact_from_single_line(raw)
                if m_contact:
                    result["联系人"] = m_contact
                    raw = raw[: raw.rfind(m_contact)]

            result["发货地址"] = self._clean_address_text(raw)
           
            return result
        
        return result
    
   

    # ----------------------------
    # 项目解析（多页安全）
    # ----------------------------
    """
    def _parse_items(self) -> List[Dict]:
        items = []
        i = 0

        while i < len(self.lines):
            m = ITEM_LINE_RE.match(self.lines[i])
            if not m:
                i += 1
                continue

            item = {
                "项目行号": m.group(1),
                "零件号": m.group(2),
                "名字": "",
                "贵方零件号": "",
                "贵方订单号": "",
                "要求到货日期": "",
                "数量": "",
                "Our Order No.": ""
            }

            rest = m.group(3)
            qty = re.search(r"(\d+)\s*EA", rest)
            if qty:
                item["数量"] = qty.group(1)
                item["名字"] = rest[:qty.start()].strip()
            else:
                item["名字"] = rest.strip()

            j = i + 1


            # 第一子行：按位置切割
            if j < len(self.lines) and not ITEM_LINE_RE.match(self.lines[j]):
                sub = self.lines[j]
                nums = re.findall(r"\b[A-Z0-9\-]{6,}\b", sub)

                if len(nums) >= 1:
                    item["贵方零件号"] = nums[0]
                if len(nums) >= 2:
                    item["贵方订单号"] = nums[1]
                if len(nums) >= 3:
                    item["Our Order No."] = nums[-1]

                j += 1
                     
                       
            # 吞剩余行（日期等）
            while j < len(self.lines) and not ITEM_LINE_RE.match(self.lines[j]):
                m_date = DATE_RE.search(self.lines[j])
                if m_date:
                    item["要求到货日期"] = m_date.group()
                j += 1

            items.append(item)
            i = j

        return items
        """
    def _parse_items(self) -> List[Dict]:
        items = []
        i = 0

        while i < len(self.raw_lines):
            m = ITEM_LINE_RE.match(self.raw_lines[i])
            if not m:
                i += 1
                continue

            # ===============================
            # 1️⃣ 项目主行
            # ===============================
            item = {
                "项目行号": m.group(1),
                "零件号": m.group(2),
                "名字": "",
                "贵方零件号": "",
                "贵方订单号": "",
                "Our Order No.": "",
                "要求到货日期": "",
                "数量": ""
            }

            main_line = self.raw_lines[i]

            rest = m.group(3)

            # 1️⃣ 数量
            qty = re.search(r"(\d+)\s*EA", rest)
            if qty:
                item["数量"] = qty.group(1)

            # 2️⃣ 国家（不写死）
            m_country = re.search(r"\b[A-Z]{2}\b", rest)

            # 3️⃣ 名字的边界规则
            if m_country:
                # 名字在 国家 之前
                item["名字"] = rest[:m_country.start()].strip()
            elif qty:
                # fallback：没有国家，用 EA
                item["名字"] = rest[:qty.start()].strip()
            else:
                item["名字"] = rest.strip()

            # 4️⃣ 统一清洗
            item["名字"] = self._clean_text(item["名字"])
                       

            # ===============================
            # 2️⃣ 计算列起始位置（基于主行）
            # ===============================
            # 核心思想：后续子行按这些 index 对齐切割
            col_pos = {
                "part_no": main_line.find(item["零件号"]),
                "name": main_line.find(item["名字"]) if item["名字"] else None,
                "country": main_line.find("CN") if "CN" in main_line else None,
            }

            # fallback：防止 find 失败
            col_pos["name"] = col_pos["name"] if col_pos["name"] != -1 else None
            col_pos["country"] = col_pos["country"] if col_pos["country"] != -1 else None

            # ===============================
            # 3️⃣ 扫描子行区块（订单 / 日期 / colli）
            # ===============================
            j = i + 1
            order_parsed = False

            while j < len(self.raw_lines) and not ITEM_LINE_RE.match(self.raw_lines[j]):
                line = self.raw_lines[j]

                # ---------- 3.1 订单子行（按列切割，只解析一次） ----------
                if not order_parsed:
                    # ✅ 用“多空格分列”解析订单子行
                    cols = re.split(r"\s{2,}", line.strip())
                    cols = [c for c in cols if c]

                    # 从右往左找 Our Order No.（必须是纯数字）
                    for idx in range(len(cols) - 1, -1, -1):
                        if re.fullmatch(r"\d{6,}", cols[idx]):
                            item["Our Order No."] = cols[idx]

                            left = cols[:idx]

                            if left:
                                item["贵方订单号"] = self._clean_text(left[-1])
                            if len(left) >= 2:
                                item["贵方零件号"] = self._clean_text(left[-2])

                            order_parsed = True
                            j += 1
                            break

                    if order_parsed:
                        continue

                # ---------- 3.2 日期行 ----------
                m_date = DATE_RE.search(line)
                if m_date:
                    item["要求到货日期"] = m_date.group()
                    j += 1
                    continue

                # ---------- 3.3 其它说明行（colli 等） ----------
                j += 1

            # ===============================
            # 4️⃣ 收尾
            # ===============================
            items.append(item)
            i = j  # 跳到下一个 ITEM

        return items

# ----------------------------
# CLI
# ----------------------------

def process_all_htm_files(input_dir: str, output_dir: str, config: dict):
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(input_dir):
        if not file.lower().endswith(".htm"):
            continue

        path = os.path.join(input_dir, file)
        parser = DeliveryNoteParser(path, config)
        result = parser.parse()

        out_path = os.path.join(output_dir, file.replace(".htm", ".json"))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"[OK] {file} -> {out_path}")


if __name__ == "__main__":
        
    cfg = load_config()
    
    input_dir = cfg["paths"].get("input_dir", "Docs")
    output_dir = cfg["paths"].get("output_dir", "Output")

    process_all_htm_files(input_dir, output_dir, cfg)
    