# Delivery Note HTM 解析器

用于将Docs文件夹下的htm格式送货单文件转换为JSON格式的工具。

## 功能特性

- 解析HTM格式的Delivery Note文件
- 提取关键信息(DN号、日期、物料号、数量等)
- 转换为结构化的JSON格式输出
- 支持批量处理多个文件

## 环境要求

- Python 3.6+
- 依赖包见 `requirements.txt`

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 方式1: 直接运行脚本

```bash
python htm_parser.py
```

这将:
1. 自动扫描 `Docs` 目录下所有htm/html文件
2. 解析每个文件并提取信息
3. 在当前目录生成 `delivery_notes.json` 文件

### 方式2: 作为模块使用

```python
from htm_parser import DeliveryNoteParser, process_all_htm_files

# 解析单个文件
parser = DeliveryNoteParser()
result = parser.parse_htm_file('path/to/file.htm')

# 批量处理
process_all_htm_files('Docs', 'output.json')
```

## 输出格式

生成的JSON文件包含以下字段:

```json
{
  "file_name": "文件名",
  "DN号": "送货单号",
  "日期": "日期",
  "客户代码": "客户代码",
  "客户编号": "客户编号",
  "客户物料号": "客户物料号",
  "送货地址": "送货地址",
  "收货人": "收货人",
  "联系电话": "联系电话",
  "ZF物料号": "ZF物料号",
  "零件号": "零件号",
  "名字": "产品名称",
  "数量": "数量",
  "净重": "净重",
  "毛重": "毛重",
  "包装": "包装信息",
  "项目": [
    {
      "raw": "原始数据"
    }
  ]
}
```

## 参考文件

- `Docs/DN内容.xlsx`: 定义了需要提取的字段结构

## 目录结构

```
DeliveryNote/
├── Docs/                      # 存放HTM源文件
│   ├── Delivery Note 78018807 .htm
│   └── DN内容.xlsx
├── htm_parser.py             # 主解析脚本
├── requirements.txt          # Python依赖
├── delivery_notes.json       # 输出的JSON文件(生成)
└── README.md                # 说明文档
```

## 开发说明

解析器使用BeautifulSoup库解析HTML,通过正则表达式提取需要的字段。
如果需要调整提取逻辑,可以修改 `htm_parser.py` 中对应的 `_extract_*` 方法。

## License

MIT
