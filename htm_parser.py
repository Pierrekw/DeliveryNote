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

import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

def setup_logger():
    base_path = get_base_path()
    log_dir = os.path.join(base_path, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(
        log_dir,
        f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 防止重复添加 handler（pyinstaller 有时会发生）
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件日志（按天滚动，保留 14 天）
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        delay=True       #关键：防止 Windows 文件锁问题
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 控制台日志（方便调试 exe）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def apply_log_level(config):
    level = config.get("log", {}).get("level", "INFO").upper()
    logging.getLogger().setLevel(
        getattr(logging, level, logging.INFO)
    )

def get_base_path():
    """
    兼容：
    - python htm_parser.py
    - 打包后的 htm_parser.exe
    """
    if getattr(sys, 'frozen', False):
        # exe 运行目录
        return os.path.dirname(sys.executable)
    else:
        # 脚本运行目录
        return os.path.dirname(os.path.abspath(__file__))

def load_config(config_path: str = "config.yaml") -> dict:
    base_path = get_base_path()
    full_config_path = os.path.join(base_path, config_path)

    default_config = {
        "paths": {
            "input_dir": "Input",
            "output_dir": "Output"
        },
        "process": {
            "overwrite": False
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
    
    logger = logging.getLogger()

    if not os.path.exists(full_config_path):
        logger.warning(f"Config not found, using default: {full_config_path}")
        return default_config

    logger.info(f"Config loaded from: {full_config_path}")   

    with open(full_config_path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}

    # 浅合并（目前够用）
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

        # ✅ 提取公司表头信息
        header_lines = self.extract_header_block()
        company_info = self.parse_company_from_header(header_lines)
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
            "项目": self._parse_items(),
            "公司": company_info
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
    
    def extract_header_block(self) -> list:
        # ✅ 已缓存直接返回
        if hasattr(self, "_header_lines") and self._header_lines:
            return self._header_lines

        header_lines = []

        for line in self.lines:
            # ✅ ✅ 优先使用“下划线”为分界（更稳）
            if re.match(r'^\s*_+\s*$', line):
                break

            # ✅ fallback：发货单分界
            if re.search(r'(发货单|Delivery\s*note)', line, re.I):
                break

            # ✅ 跳过 Copy
            if line.lower() == "copy":
                continue

            header_lines.append(line)

            if len(header_lines) > 60:
                break

        self._header_lines = header_lines
        return header_lines


    def parse_company_from_header(self, header_lines: List[str]) -> dict:
        company_name = ""
        address = ""
        phone = ""
        fax = ""

        merged_line = ""
        debug_line = ""

        # ✅ Step1：找分隔线
        sep_idx = -1
        for i, line in enumerate(header_lines):
            if re.match(r'^\s*_+\s*$', line):
                sep_idx = i
                break

        # ✅ Step2：取分隔线上面的 block（最多2行有效地址）
        if sep_idx > 1:
            block = []

            # ✅ 固定取分隔线上面2行（不做复杂过滤）
            for j in range(sep_idx - 1, sep_idx - 3, -1):
                if j >= 0:
                    l = header_lines[j].strip()

                    if not l:
                        continue
                    
                    # ❌ 只排除电话传真
                    if re.search(r'(电话|传真|Tel|Fax)', l, re.I):
                        continue

                    block.append(l)

            block.reverse()

            merged_line = " ".join(block)
            merged_line = re.sub(r'\s+', ' ', merged_line).strip()
            debug_line = merged_line


        # ✅ ✅ fallback（没有分隔线）
        elif len(header_lines) >= 2:
            block = header_lines[-2:]
            merged_line = " ".join(block)
            merged_line = re.sub(r'\s+', ' ', merged_line).strip()

        debug_line = merged_line

        # ✅ ✅ ✅ Step3：优先解析 merged_line
        if merged_line:
            line = merged_line.replace("，", ",")

            parts = re.split(r'(有限公司|Co\.?,?\s*Ltd\.?)', line)

            if len(parts) >= 3:
                company_name = (parts[0] + parts[1]).strip()
                address = parts[2].strip(" ,")

                # ✅ 如果 address 不像地址 → 强制清空
                if address and not re.search(r'(路|号|Street|Road|\d{5,})', address):
                    address = ""

        # ✅ ✅ ✅ Step4：fallback（地址补全）
        if not address:
            capturing = False
            addr_parts = []

            for line in header_lines:

                if re.search(r'(地址[:：]|Address)', line):
                    capturing = True

                    addr = re.sub(r'.*(地址[:：]|Address)', '', line).strip()
                    if addr:
                        addr_parts.append(addr)
                    continue

                if capturing:
                    if re.search(r'(电话|传真|Tel|Fax)', line, re.I):
                        break
                    if re.match(r'^_+$', line):
                        break

                    addr_parts.append(line)

            address = " ".join(addr_parts)

        # ✅ ✅ ✅ Step5：fallback（公司名）
        if not company_name:
            for i, line in enumerate(header_lines[:10]):

                if re.search(r'(Report|Copy|Page)', line, re.I):
                    continue
                if re.match(r'^_+$', line):
                    continue

                if len(line) >= 4:
                    company_name = line

                    if i + 1 < len(header_lines):
                        next_line = header_lines[i + 1]
                        if re.fullmatch(r'(有限公司|公司)', next_line):
                            company_name += next_line

                    break

        # ✅ ✅ ✅ Step6：电话 / 传真
        for line in header_lines:
            if not phone and re.search(r'(电话|Tel|Telephone)', line, re.I):
                m = re.search(r'(\(?\+?\d+\)?[\d\s\-]{6,})', line)
                if m:
                    phone = m.group(1).strip()

            if not fax and re.search(r'(传真|Fax)', line, re.I):
                m = re.search(r'(\(?\+?\d+\)?[\d\s\-/]{6,})', line)
                if m:
                    fax = m.group(1).strip()

        # ✅ ✅ ✅ Step7：清洗
        address = address.replace("商 务", "商务")
        address = address.replace("中 心", "中心")
        address = address.replace("国 际", "国际")

        address = re.sub(r'_+', '', address)
        address = re.sub(r'\s+', ' ', address).strip()

        return {
            "name": company_name.strip(),
            "address": address,
            "phone": phone,
            "fax": fax,
            #debug only
            #"_merged_line_debug": debug_line
        }
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
    
    def _parse_items(self) -> List[Dict]:
        items = []
        i = 0

        while i < len(self.raw_lines):
            m = ITEM_LINE_RE.match(self.raw_lines[i])
            if not m:
                i += 1
                continue

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

            rest = m.group(3)

            # ---------- 数量 ----------
            qty = re.search(r"(\d+)\s*EA", rest)
            if qty:
                item["数量"] = qty.group(1)

            # ---------- 国家（不写死） ----------
            m_country = re.search(r"\b[A-Z]{2}\b", rest)

            # ---------- 名字边界 ----------
            if m_country:
                item["名字"] = rest[:m_country.start()].strip()
            elif qty:
                item["名字"] = rest[:qty.start()].strip()
            else:
                item["名字"] = rest.strip()

            item["名字"] = self._clean_text(item["名字"])

            # ---------- 扫描子行 ----------
            j = i + 1

            while j < len(self.raw_lines) and not ITEM_LINE_RE.match(self.raw_lines[j]):
                line = self.raw_lines[j].strip()

                # 🚧 项目内硬边界：colli
                if line.lower().startswith("colli"):
                    break  # ✅ 当前项目结束，直接跳出子行扫描

                # ✅ 订单子行解析（只要 Our Order No. 还没拿到就继续）
                if not item["Our Order No."]:
                    cols = re.split(r"\s{2,}", line)
                    cols = [c for c in cols if c]

                    found = False

                    # 1️⃣ 表格对齐型（多空格）
                    for idx in range(len(cols) - 1, -1, -1):
                        if re.fullmatch(r"\d{6,}", cols[idx]):
                            item["Our Order No."] = cols[idx]

                            left = cols[:idx]
                            if left:
                                item["贵方订单号"] = self._clean_text(left[-1])
                            if len(left) >= 2:
                                item["贵方零件号"] = self._clean_text(left[-2])

                            found = True
                            break

                    # 2️⃣ fallback：单空格压缩型（6275）
                    if not found:
                        nums = re.findall(r"\b\d{6,}\b", line)
                        if nums:
                            item["Our Order No."] = nums[-1]

                            prefix = line[:line.rfind(nums[-1])].strip()
                            parts = prefix.split()

                            if parts:
                                item["贵方订单号"] = self._clean_text(parts[-1])
                            if len(parts) >= 2:
                                item["贵方零件号"] = self._clean_text(parts[-2])

                # ✅ 日期行
                m_date = DATE_RE.search(line)
                if m_date:
                    item["要求到货日期"] = m_date.group()

                j += 1

            items.append(item)
            i = j

        return items    
    

# ----------------------------
# CLI
# ----------------------------

def process_all_htm_files(input_dir: str, output_dir: str, config: dict):
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(input_dir):
        if not file.lower().endswith(".htm"):
            continue
        
        try:
        
            path = os.path.join(input_dir, file)
            parser = DeliveryNoteParser(path, config)
            result = parser.parse()

            out_path = os.path.join(output_dir, file.replace(".htm", ".json"))
            
            overwrite = config.get("process", {}).get("overwrite", False)
   
            if os.path.exists(out_path) and overwrite:
                bak = out_path + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.replace(out_path, bak)
                logger.warning(f"[BACKUP] {out_path} -> {bak}")
            
            if os.path.exists(out_path) and not overwrite:
                logger.info(f"[SKIP] {file} already parsed-> {out_path} ")
                continue
            
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[OK] {file} -> {out_path}")  

        except Exception:
            logger.exception(f"[FAIL]{file}")



# ----------------------------
# Main
# ----------------------------
def main():
    
    logger.info("Program started")
    logger.info(f"Base path: {get_base_path()}")
    logger.info(f"Python version: {sys.version}")

    cfg = load_config()
    apply_log_level(cfg)
    
    """
    logger.debug(
        f"Config summary: paths={cfg.get('paths')}, "
        f"remark_keys={cfg.get('keywords', {}).get('remark_start')}"
    )
    """
    
    input_dir = cfg["paths"].get("input_dir", "Input")
    output_dir = cfg["paths"].get("output_dir", "Output")
    
    if not os.path.exists(input_dir):
        logger.error(f"Input directory not found: {input_dir}")
        return
    
    logger.info(f"Input_dir : {input_dir}")
    logger.info(f"Output_dir: {output_dir}")

    try:
        # 核心解析逻辑
        process_all_htm_files(input_dir, output_dir, cfg)
        
    except Exception as e:
        logger.exception("Unexpected error while parsing file")

    logger.info("Program finished")

if __name__ == "__main__":
        
    logger = setup_logger()
        
    main()
    
    