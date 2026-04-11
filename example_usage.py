"""
示例脚本: 展示如何使用HTM解析器
"""

import os
import json
from htm_parser import DeliveryNoteParser, process_all_htm_files


def main():
    """主函数"""
    print("=" * 60)
    print("Delivery Note HTM 解析器 - 示例")
    print("=" * 60)
    
    # 设置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(current_dir, 'Docs')
    
    # 检查Docs目录是否存在
    if not os.path.exists(docs_dir):
        print(f"\n错误: 找不到Docs目录: {docs_dir}")
        return
    
    # 处理所有HTM文件
    print(f"\n扫描目录: {docs_dir}")
    results = process_all_htm_files(docs_dir, 'delivery_notes.json')
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("解析统计")
    print("=" * 60)
    print(f"处理文件数: {len(results)}")
    
    # 显示每个文件的摘要
    for idx, result in enumerate(results, 1):
        print(f"\n文件 {idx}:")
        print(f"  文件名: {result.get('file_name', 'N/A')}")
        print(f"  DN号: {result.get('DN号', 'N/A')}")
        print(f"  日期: {result.get('日期', 'N/A')}")
        print(f"  净重: {result.get('净重', 'N/A')[:30] if result.get('净重') else 'N/A'}")
        print(f"  毛重: {result.get('毛重', 'N/A')[:30] if result.get('毛重') else 'N/A'}")
        
        # 显示项目数量
        items = result.get('项目', [])
        if items:
            print(f"  项目数: {len(items)}")
            # 显示第一个项目的详细信息
            if isinstance(items[0], dict) and 'material_no' in items[0]:
                print(f"\n  第一个项目示例:")
                print(f"    行号: {items[0].get('line_no', 'N/A')}")
                print(f"    物料号: {items[0].get('material_no', 'N/A')}")
                print(f"    描述: {items[0].get('description', 'N/A')}")
                print(f"    原产国: {items[0].get('origin', 'N/A')}")
                print(f"    数量: {items[0].get('quantity', 'N/A')}")
    
    print("\n" + "=" * 60)
    print(f"结果已保存到: {os.path.join(current_dir, 'delivery_notes.json')}")
    print("=" * 60)


if __name__ == '__main__':
    main()
