# Delivery Note HTM → JSON Parser

## 📄 项目简介

`htm_parser.py` 是一个用于将 **Delivery Note（交货单）HTM 文件解析并转换为结构化 JSON 文件** 的 Python 脚本。

该脚本基于 **块级解析（Block-based）+ 位置优先（Position-first）** 的设计思路，支持：
- 多页 HTM 文件
- 中英文混合字段
- 非严格结构的 HTML 文档
- 可配置关键词与目录结构

当前版本：**V3.0**

---

## ✨ 核心功能

- 🔍 自动解析交货单中的关键信息：
  - 编号（Number）
  - 日期（Date）
  - 客户编号（Customer No.）
  - 明细行（POS / 件号 / 描述）
  - 收发货信息（联系人 / 地址 / 电话）
  - 备注信息
- 📂 批量处理指定目录下所有 `.htm` 文件
- 🧾 输出为可读、可扩展的 JSON 结构
- ⚙️ 支持通过 `config.yaml` 自定义关键词规则

---

## 🧱 项目结构

```text
.
├── htm_parser.py       # 主解析脚本
├── config.yaml         # 解析规则配置文件
├── Input/              # HTM 输入目录
└── Output/             # JSON 输出目录

若目录不存在，脚本会自动创建 Output 目录。

🛠️ 环境依赖
请确保已安装以下 Python 依赖：

pip install beautifulsoup4 pyyaml

Python 建议版本：3.8+



🚀 使用方法
1️⃣ 准备 HTM 文件

将需要解析的 Delivery Note .htm 文件放入 Input/ 目录

2️⃣（可选）修改配置文件
编辑 config.yaml，根据实际单据格式调整关键词（详见下文）
3️⃣ 运行脚本

python htm_parser.py
``
运行完成后：

所有解析结果将以 .json 文件形式输出至 Output/ 目录
文件名与原始 HTM 文件一一对应


⚙️ 配置说明（config.yaml）
默认配置结构
paths:
  input_dir: Input
  output_dir: Output

keywords:
  remark_start:
    - 备注
  remark_end:
    - 项目零件号
    - 项目
    - Pos.

  shipping:
    contact:
      - 联系人
      - 收货人
    address:
      - 发货地址
      - 收货地址
      - 地址
    phone:
      - 电话
      - 联系电话

  mark:
    - 标明
	
说明


配置项：作用
remark_start：备注内容开始的关键词
remark_end：备注内容结束的关键词
shipping.contact：联系人关键词
shipping.address：地址关键词
shipping.phone：电话关键词
mark：标记性说明字段

✅ 可根据客户模板差异，自由扩展关键词列表

📑 解析规则说明
脚本内置以下关键正则规则：

编号 / 客户编号 / 日期字段关键词
明细行解析正则
Plain Textregex isn’t fully supported. Syntax highlighting is based on Plain Text.
(\d{3})\s+([A-Z0-9]{6,})\s+(.*)

日期格式：DD.MM.YYYY
手机号：1XXXXXXXXXX
固话：支持 +86、区号、横线格式


🧾 输出示例（JSON）
{
  "number": "DN-2025-00123",
  "date": "23.04.2025",
  "customer_no": "CUST8899",
  "shipping": {
    "contact": "张三",
    "address": "上海市浦东新区...",
    "phone": "13812345678"
  },
  "items": [
    {
      "pos": "001",
      "part_no": "ABC12345",
      "description": "Motor Assembly"
    }
  ],
  "remark": "包装前请确认数量"
}


⚠️ 注意事项

本脚本适用于 结构相对稳定的 HTM 交货单
若 HTML 标签或字段位置变化较大：

可优先通过 config.yaml 调整关键词
必要时需调整正则规则


当前版本未处理：

PDF 文件
图片型扫描单据




📌 适用场景

智能工厂 / 数字化项目交货单解析
ERP / WMS 数据预处理
内部系统接口 JSON 转换
批量单据归档与数据清洗


