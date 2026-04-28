# -*- coding: utf-8 -*-
# htm_parser.py
# ==========================================
# Delivery Note HTM -> JSON Parser (V2)
# Anchor-based, language-agnostic
# ==========================================

import os
import re
import json
import sys
from bs4 import BeautifulSoup
from typing import List, Dict


# ----------------------------
# 基础正则 & 关键词
# ----------------------------

NUMBER_KEYS = ["编号", "Number"]
DATE_KEYS = ["日期", "Date"]
CUSTOMER_KEYS = ["客户编号", "Customer No."]

ITEM_LINE_RE = re.compile(r"^(\d{3})\s+(\d{8,})\s+(.*)")
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
NUMBER_8_RE = re.compile(r"\b\d{8}\b")
ORDER_NO_RE = re.compile(
    r"[A-Z]{2,}-[A-Z0-9]+-\d+(?:-\d+)?|\b\d{6,}\b"
)
YOUR_PART_NO_RE = re.compile(r"\b\d{4,}(?:-\d+)?\b")

# ----------------------------
# Parser 主类
# ----------------------------

class DeliveryNoteParser:
    def __init__(self, htm_path: str):
        self.htm_path = htm_path
        self.soup = None
        self.lines: List[str] = []

    # ---------
    # 主入口
    # ---------

    def parse(self) -> Dict:
        self._load()
        self._normalize_lines()

        shipping_info = self._extract_shipping_info()       
        
        result = {
            "file_name": os.path.basename(self.htm_path),
            "编号": self._extract_number(),
            "日期": self._extract_date(),
            "客户编号": self._extract_customer_no(),
            "发货地址": shipping_info["发货地址"],
            "联系人": shipping_info["联系人"],
            "联系电话": shipping_info["联系电话"],
            "标明": self._extract_remark(),
            "项目": self._parse_items()
        }
        return result

    # ----------------------------
    # HTM / 文本预处理
    # ----------------------------

    def _load(self):
        with open(self.htm_path, "r", encoding="utf-8", errors="ignore") as f:
            self.soup = BeautifulSoup(f, "html.parser")

    def _normalize_lines(self):
        raw = self.soup.get_text(separator="\n")
        self.lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in raw.split("\n")
            if line.strip()
        ]

    # ----------------------------
    # 通用字段抽取工具
    # ----------------------------

    def _search_by_anchor(self, keys, pattern):
        for i, line in enumerate(self.lines):
            if any(k in line for k in keys):
                for j in range(i, min(i + 3, len(self.lines))):
                    m = re.search(pattern, self.lines[j])
                    if m:
                        return m.group()
        return ""

    # ----------------------------
    # 基础字段解析
    # ----------------------------

    def _extract_number(self) -> str:
        return self._search_by_anchor(NUMBER_KEYS, NUMBER_8_RE)

    def _extract_date(self) -> str:
        return self._search_by_anchor(DATE_KEYS, DATE_RE)

    def _extract_customer_no(self) -> str:
        return self._search_by_anchor(CUSTOMER_KEYS, r"\b[A-Z0-9]{4,}\b")

    # ----------------------------
    # 中文订单特有字段
    # ----------------------------

    def _extract_remark(self) -> str:
        """
        从“备注”区块中提取“标明：”后的内容
        支持多行
        """
        in_remark = False
        remark_lines = []

        for line in self.lines:
            # 1️⃣ 进入备注区块
            if line.startswith("备注"):
                in_remark = True
                continue

            # 2️⃣ 离开备注区块（遇到下一个明显的分隔）
            if in_remark and (
                line.startswith("项目") or
                line.startswith("Pos.") or
                line.startswith("Your contact") or
                line.startswith("项目零件号")
            ):
                break

            # 3️⃣ 收集备注内容
            if in_remark:
                remark_lines.append(line)

        # 4️⃣ 在备注区块中查找“标明”
        for line in remark_lines:
            if "标明：" in line:
                return line.split("标明：", 1)[1].strip()

        return ""

    def _extract_shipping_info(self) -> dict:
        """
        从“发货地址”相关文本中解析：
        - 发货地址
        - 联系人
        - 联系电话（手机 / 座机）
        """
        result = {
            "发货地址": "",
            "联系人": "",
            "联系电话": ""
        }

        # 1️⃣ 先找到包含“发货地址”的原始行
        raw = ""
        for line in self.lines:
            if "发货地址：" in line:
                raw = line.split("发货地址：", 1)[1].strip()
                break

        if not raw:
            return result

        working = raw

        # 2️⃣ 提取电话：先手机号，再座机
        m_phone = re.search(r"\b1\d{10}\b", working)
        if not m_phone:
            m_phone = re.search(r"\b(?:\+86\s?)?0\d{2,3}[-\s]?\d{7,8}\b", working)

        if m_phone:
            result["联系电话"] = m_phone.group()
            before_phone = working[:m_phone.start()]
        else:
            before_phone = working

        # 3️⃣ 提取联系人（通常在电话前，2-3 个中文）
        m_contact = re.search(r"([\u4e00-\u9fa5]{2,3})[,，；;\s]*$", before_phone)
        if m_contact:
            result["联系人"] = m_contact.group(1)
            address_part = before_phone[:m_contact.start()]
        else:
            address_part = before_phone

        # 4️⃣ 剩余就是发货地址
        result["发货地址"] = address_part.strip(" ,，；;")

        return result

    # ----------------------------
    # 项目解析（核心）
    # ----------------------------

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

            # 名字 + 数量
            qty = re.search(r"(\d+)\s*EA", rest)
            if qty:
                item["数量"] = qty.group(1)
                item["名字"] = rest[:qty.start()].strip()
            else:
                item["名字"] = rest.strip()

            # 吞后续行
            j = i + 1

            # ---------- 第一子行：优先解析 贵方零件号 / 订单号 ----------
            # 项目号下一行固定结构：
            # [贵方零件号] [贵方订单号] [Our Order No.]
            
            if j < len(self.lines) and not ITEM_LINE_RE.match(self.lines[j]):
                sub = self.lines[j]

                
                # 1提取第一个数字块 → 贵方零件号
                m_first = re.search(r"\b\d[\d-]{3,}\b", sub)
                if m_first:
                    item["贵方零件号"] = m_first.group()
                    rest = sub[m_first.end():]
                else:
                    rest = sub

                # 2️在剩余部分中，提取下一个“非空字段” → 贵方订单号
                m_order = re.search(r"\b[A-Z0-9][A-Z0-9\-]{3,}\b", rest)
                if m_order:
                    item["贵方订单号"] = m_order.group()

                # 3️提取最后一个较长数字 → Our Order No.
                nums = re.findall(r"\b\d{6,}\b", sub)
                if nums:
                    item["Our Order No."] = nums[-1]


                j += 1

            # ---------- 吞剩余行：补漏 ----------
            while j < len(self.lines) and not ITEM_LINE_RE.match(self.lines[j]):
                line = self.lines[j]

                if not item["要求到货日期"]:
                    m = DATE_RE.search(line)
                    if m:
                        item["要求到货日期"] = m.group()

                j += 1

            items.append(item)
            i = j

        return items


# ----------------------------
# CLI 批量处理
# ----------------------------

def process_all_htm_files(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(input_dir):
        if not file.lower().endswith(".htm"):
            continue

        path = os.path.join(input_dir, file)
        parser = DeliveryNoteParser(path)
        result = parser.parse()

        out_path = os.path.join(output_dir, file.replace(".htm", ".json"))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"[OK] {file} -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python htm_parser.py <input_dir> <output_dir>")
        sys.exit(1)

    process_all_htm_files(sys.argv[1], sys.argv[2])