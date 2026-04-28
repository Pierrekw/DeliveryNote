"""  
Delivery Note HTM 文件解析器
将HTM格式的送货单文件转换为JSON格式
"""

import os
import re
import json
import sys
from bs4 import BeautifulSoup
from typing import Dict, List, Any

# 设置标准输出编码为UTF-8
if sys.platform == 'win32' and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
    except (AttributeError, IOError):
        pass  # 兼容旧版本Python


class DeliveryNoteParser:
    """送货单解析器"""
    
    def __init__(self):
        # 定义需要提取的字段映射
        self.fields_mapping = {
            '编号': '',           # DN号
            '客户编号': '',            
            '发货地址': '',       # 发货地址
            '联系人': '',           #备注中增加联系人：
            '联系电话': '',          # 备注中联系电话：
            '标明': '',          # 特殊标记信息
            '项目': [],          # 项目列表
        }
    
    def parse_htm_file(self, file_path: str) -> Dict[str, Any]:
        """
        解析单个HTM文件
        
        Args:
            file_path: HTM文件路径
            
        Returns:
            包含提取信息的字典
        """
        # 尝试多种编码读取文件
        content = None
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                print(f"成功使用 {enc} 编码读取文件")
                break
            except Exception as e:
                continue
        
        if content is None:
            # 如果都失败,使用utf-8并忽略错误
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            print("使用 utf-8 编码读取文件(忽略错误)")
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 提取所有<nobr>标签的文本,保持行结构
        lines = []
        for nobr in soup.find_all('nobr'):
            text = nobr.get_text().strip()
            if text:
                # HTML实体解码
                import html
                text = html.unescape(text)
                lines.append(text)
        
        full_text = '\n'.join(lines)
        
        # 提取信息
        delivery_note = {
            'file_name': os.path.basename(file_path),
            '编号': self._extract_dn_number(lines),
            '日期': self._extract_date(lines),
            '客户编号': self._extract_customer_number(lines),
            '发货地址': self._extract_shipping_address(lines),
            '联系人': self._extract_contact_person(lines),
            '联系电话': self._extract_phone(lines),
            '标明': self._extract_mark_info(lines),
            '项目': self._extract_items(lines),
        }
        
        return delivery_note
    
    def _extract_dn_number(self, lines: List[str]) -> str:
        """提取编号(DN号)"""
        # 查找"编号"标签行,提取下一行行首到空格的内容
        for i, line in enumerate(lines):
            if '编号' in line and '客户' not in line:
                # 下一行: "78018807    05.02.2026"
                if i + 1 < len(lines):
                    # 提取行首到第一个空格的内容
                    match = re.match(r'^([^\s]+)', lines[i + 1])
                    if match:
                        return match.group(1)
        return ''
    
    def _extract_date(self, lines: List[str]) -> str:
        """提取日期"""
        # 查找"编号"标签行,下一行包含编号和日期(按列对齐)
        # 行15: "编号        日期"
        # 行16: "78018807    05.02.2026"
        for i, line in enumerate(lines):
            if '编号' in line and '客户' not in line:
                # 下一行: 第一个空格后的内容是日期
                if i + 1 < len(lines):
                    # 按空格分割,取第二部分
                    parts = lines[i + 1].split()
                    if len(parts) >= 2:
                        return parts[1]  # 第二列是日期
        return ''
    
    def _extract_customer_number(self, lines: List[str]) -> str:
        """提取客户编号"""
        # 查找"客户编号"标签行,下一行即为客户编号
        # 行17: "客户编号"
        # 行18: "110310"
        for i, line in enumerate(lines):
            if '客户编号' in line:
                # 下一行: 行首到空格的内容
                if i + 1 < len(lines):
                    match = re.match(r'^([^\s]+)', lines[i + 1])
                    if match:
                        return match.group(1)
        return ''
    
    def _extract_customer_part_number(self, lines: List[str]) -> str:
        """提取贵方零件号"""
        for line in lines:
            if 'THT-WABCO' in line:
                match = re.search(r'(THT-WABCO-\d+-\d+)', line)
                if match:
                    return match.group(1)
        return ''
    
        
    def _extract_shipping_address(self, lines: List[str]) -> str:
        """提取发货地址"""
        for line in lines:
            if '发货地址' in line:
                # 提取: 发货地址：江苏省扬州市临江路9号,扬州中集通华专用车有限公司
                match = re.search(r'发货地址[：:]\s*([^；;]+)', line)
                if match:
                    return match.group(1).strip()
        return ''
    
    def _extract_contact_person(self, lines: List[str]) -> str:
        """提取联系人"""
        # 从发货地址行提取: "发货地址：xxx；王凯，13773583079"
        for line in lines:
            if '发货地址' in line:
                # 提取分号后的第一个人名(逗号之前)
                match = re.search(r'[；;]\s*([^，,\d]+)[，,]', line)
                if match:
                    return match.group(1).strip()
        return ''
    
        
    def _extract_phone(self, lines: List[str]) -> str:
        """提取联系电话"""
        # 从发货地址行提取电话(手机号或座机号都在同一行)
        for line in lines:
            if '发货地址' in line:
                # 优先提取11位手机号
                match = re.search(r'(1[3-9]\d{9})', line)
                if match:
                    return match.group(1)
                
                # 备用:提取座机号(021-33382000格式),在同一行
                match = re.search(r'(\d{3,4}-\d{7,8})', line)
                if match:
                    return match.group(1)
        
        return ''
    
    def _extract_mark_info(self, lines: List[str]) -> str:
        """提取标明信息(从备注部分)"""
        for line in lines:
            if '标明' in line and '20601-0196' in line:
                # 提取: 标明：20601-0196，4S/2M 24V EBS 空悬（分断线）+磨损+5公里；发货时带随货清单，随货带产品检测报告。
                match = re.search(r'标明[：:]\s*(.+?)(?:[。]|$)', line)
                if match:
                    return match.group(1).strip()
        return ''
    
    def _extract_zf_material_number(self, text: str) -> str:
        """提取ZF物料号"""
        match = re.search(r'ZF\s*物料号[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_part_number(self, text: str) -> str:
        """提取零件号"""
        match = re.search(r'零件号[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_name(self, text: str) -> str:
        """提取名字"""
        match = re.search(r'名字[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_quantity(self, text: str) -> str:
        """提取数量"""
        match = re.search(r'数量[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_net_weight(self, text: str) -> str:
        """提取净重"""
        match = re.search(r'Net\s*weight[:\s]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_gross_weight(self, text: str) -> str:
        """提取毛重"""
        match = re.search(r'Gross\s*weight[:\s]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_packing(self, text: str) -> str:
        """提取包装信息"""
        match = re.search(r'Packing[:\s]*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_items(self, lines: List[str]) -> List[Dict[str, str]]:
        """
        提取项目列表
        每个项目包含:
        - 项目行号 (010, 020, 030...)
        - 零件号
        - 名字(描述)
        - 贵方零件号
        - 贵方订单号
        - 要求到货日期
        - 数量
        - Our Order No.
        """
        items = []
        current_item = None
        
        for i, line in enumerate(lines):
            # 匹配项目行号开头 (如: 010, 020, 030...)
            # 格式: 010 4491331200          VCSII Power Cable (12.0mCN                28EA
            line_no_match = re.match(r'^\s*(\d{3})\s+(\d+)\s+(.+)$', line)
            
            if line_no_match:
                # 新项目开始
                if current_item:
                    items.append(current_item)
                
                # 提取项目名称(去除原产国和数量)
                full_name = line_no_match.group(3).strip()
                # 去除末尾的原产国代码(CN/DE/PL/SE等)和数量
                clean_name = re.sub(r'\s+(CN|DE|PL|SE|FR)\s+\d+EA.*$', '', full_name)
                clean_name = re.sub(r'\s+\d+EA.*$', '', clean_name)
                
                current_item = {
                    '项目行号': line_no_match.group(1),
                    '零件号': line_no_match.group(2),
                    '名字': clean_name.strip(),
                    '贵方零件号': '',
                    '贵方订单号': '',
                    '要求到货日期': '',
                    '数量': '',
                    'Our Order No.': ''
                }
            elif current_item:
                # 继续解析当前项目的其他信息
                # 第一行补充信息: 20601-0196            THT-WABCO-250148-2   115791363
                if not current_item['贵方零件号'] and re.match(r'^\s*\d+-\d+', line):
                    match = re.match(r'\s*(\d+-\d+)\s+([\w-]+)\s+(\d+)', line)
                    if match:
                        current_item['贵方零件号'] = match.group(1)
                        current_item['贵方订单号'] = match.group(2)
                        current_item['Our Order No.'] = match.group(3)
                
                # 第二行: 日期 27.01.2026
                elif not current_item['要求到货日期'] and re.match(r'^\s*\d{2}\.\d{2}\.\d{4}', line):
                    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', line)
                    if match:
                        current_item['要求到货日期'] = match.group(1)
                
                # colli行: colli: 173550616                     28 EA
                elif 'colli' in line:
                    qty_match = re.search(r'(\d+)\s*EA', line)
                    if qty_match:
                        current_item['数量'] = qty_match.group(1)
        
        # 添加最后一个项目
        if current_item:
            items.append(current_item)
        
        return items


def process_all_htm_files(docs_dir: str):
    """
    处理目录下所有HTM文件,每个文件生成独立的JSON
    
    Args:
        docs_dir: Docs目录路径
    """
    parser = DeliveryNoteParser()
    delivery_notes = []
    
    # 遍历Docs目录
    for file_name in os.listdir(docs_dir):
        if file_name.endswith('.htm') or file_name.endswith('.html'):
            file_path = os.path.join(docs_dir, file_name)
            print(f'正在解析: {file_name}')
            
            try:
                delivery_note = parser.parse_htm_file(file_path)
                delivery_notes.append(delivery_note)
                
                # 生成独立的JSON文件,文件名包含编号
                dn_number = delivery_note.get('编号', 'unknown')
                json_file_name = f'{dn_number}.json'
                json_file_path = os.path.join(os.path.dirname(docs_dir), json_file_name)
                
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(delivery_note, f, ensure_ascii=False, indent=2)
                
                print(f'  ✓ 已生成: {json_file_name}')
                
            except Exception as e:
                print(f'  ✗ 解析失败 {file_name}: {str(e)}')
    
    print(f'\n解析完成! 共处理 {len(delivery_notes)} 个文件')
    
    return delivery_notes


if __name__ == '__main__':
    # 设置UTF-8输出编码
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # 设置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(current_dir, 'Docs')
    
    # 处理所有HTM文件
    results = process_all_htm_files(docs_dir)
    
    # 打印示例结果
    if results:
        print('\n示例数据:')
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
