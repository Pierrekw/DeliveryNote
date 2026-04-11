"""
Delivery Note HTM 文件解析器
将HTM格式的送货单文件转换为JSON格式
"""

import os
import re
import json
from bs4 import BeautifulSoup
from typing import Dict, List, Any


class DeliveryNoteParser:
    """送货单解析器"""
    
    def __init__(self):
        # 定义需要提取的字段映射
        self.fields_mapping = {
            'DN号': r'78018807',  # DN号模式
            '客户代码': '',
            '客户编号': '',
            '客户物料号': '',
            '送货地址': '',
            '收货人': '',
            '联系电话': '',
            'ZF物料号': '',
            '零件号': '',
            '名字': '',
            '数量': '',
            '净重': '',
            '毛重': '',
            '日期': '',
        }
    
    def parse_htm_file(self, file_path: str) -> Dict[str, Any]:
        """
        解析单个HTM文件
        
        Args:
            file_path: HTM文件路径
            
        Returns:
            包含提取信息的字典
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        # 提取信息
        delivery_note = {
            'file_name': os.path.basename(file_path),
            'DN号': self._extract_dn_number(text),
            '日期': self._extract_date(text),
            '客户代码': self._extract_customer_code(text),
            '客户编号': self._extract_customer_number(text),
            '客户物料号': self._extract_customer_material_number(text),
            '送货地址': self._extract_delivery_address(text),
            '收货人': self._extract_receiver(text),
            '联系电话': self._extract_phone(text),
            'ZF物料号': self._extract_zf_material_number(text),
            '零件号': self._extract_part_number(text),
            '名字': self._extract_name(text),
            '数量': self._extract_quantity(text),
            '净重': self._extract_net_weight(text),
            '毛重': self._extract_gross_weight(text),
            '包装': self._extract_packing(text),
            '项目': self._extract_items(text),
        }
        
        return delivery_note
    
    def _extract_dn_number(self, text: str) -> str:
        """提取DN号"""
        # 查找类似 "78018807" 的数字
        match = re.search(r'78018807', text)
        if match:
            return match.group()
        return ''
    
    def _extract_date(self, text: str) -> str:
        """提取日期"""
        # 查找日期格式如 "05.02.2026"
        match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if match:
            return match.group(1)
        return ''
    
    def _extract_customer_code(self, text: str) -> str:
        """提取客户代码"""
        # 根据实际HTM内容调整正则表达式
        match = re.search(r'客户代码[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_customer_number(self, text: str) -> str:
        """提取客户编号"""
        match = re.search(r'客户编号[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_customer_material_number(self, text: str) -> str:
        """提取客户物料号"""
        match = re.search(r'客户物料号[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_delivery_address(self, text: str) -> str:
        """提取送货地址"""
        match = re.search(r'送货地址[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_receiver(self, text: str) -> str:
        """提取收货人"""
        match = re.search(r'收货人[:\s]*([^\n]+)', text)
        if match:
            return match.group(1).strip()
        return ''
    
    def _extract_phone(self, text: str) -> str:
        """提取联系电话"""
        match = re.search(r'联系电话[:\s]*([^\n]+)', text)
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
    
    def _extract_items(self, text: str) -> List[Dict[str, str]]:
        """提取项目列表"""
        items = []
        # 这里需要根据实际HTM结构调整提取逻辑
        # 示例:查找包含物料信息的行
        lines = text.split('\n')
        for line in lines:
            if re.search(r'\d{3}\s+\d+', line):
                items.append({'raw': line.strip()})
        return items


def process_all_htm_files(docs_dir: str, output_file: str = 'delivery_notes.json'):
    """
    处理目录下所有HTM文件
    
    Args:
        docs_dir: Docs目录路径
        output_file: 输出JSON文件路径
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
            except Exception as e:
                print(f'解析失败 {file_name}: {str(e)}')
    
    # 写入JSON文件
    output_path = os.path.join(os.path.dirname(docs_dir), output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(delivery_notes, f, ensure_ascii=False, indent=2)
    
    print(f'\n解析完成! 共处理 {len(delivery_notes)} 个文件')
    print(f'结果已保存到: {output_path}')
    
    return delivery_notes


if __name__ == '__main__':
    # 设置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(current_dir, 'Docs')
    
    # 处理所有HTM文件
    results = process_all_htm_files(docs_dir)
    
    # 打印示例结果
    if results:
        print('\n示例数据:')
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
