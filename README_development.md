python# Delivery Note HTM 解析器

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
1. 自动扫描 `Input/` 目录下所有htm/html文件
2. 解析每个文件并提取信息
3. 在'Output/`'目录生成 `xxx.json` 文件

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


20260423


# Delivery Note HTM → JSON Parser

一个用于解析 **SAP / ZF Delivery Note（HTM 格式）** 的 Python 解析器，  
目标是在 **模板不一致、版式变化、字段缺失、订单跨行** 的情况下，  
仍然能够 **稳定、可维护地输出结构化 JSON**。

---

## ✨ 特性概览

- ✅ 支持 HTM / HTML 格式 Delivery Note
- ✅ 支持多页（Page 1/2, 2/2）
- ✅ 支持项目多行结构
- ✅ 支持订单信息跨行（如 6275 模板）
- ✅ 支持单空格压缩订单行
- ✅ 以 `colli` 作为项目边界，避免误解析页脚/银行信息
- ✅ 自动清洗 `&nbsp;`、多余空格
- ✅ Debug / Trace 模式，方便排错和回归验证

---

## 📂 输入 / 输出

### 输入
- `Docs/` 目录下的 `.htm` / `.html` Delivery Note 文件

### 输出
- `Output/` 目录下与源文件同名的 `.json`
- UTF-8 编码，字段已清洗

---

## 🧠 核心设计思想

### 1️⃣ 双轨文本处理（非常重要）

解析过程中维护 **两套文本行**：

| 变量 | 用途 |
|----|----|
| `raw_lines` | **保留原始空格与版式**，用于项目表格解析 |
| `lines` | **压缩空格**，用于备注 / 地址 / 联系人等语义解析 |

> ❗ **绝对不要用压缩过空格的文本去解析表格结构**

---

### 2️⃣ 项目（Item）区块的结构模型

每一个项目遵循如下逻辑结构：

```

项目主行
订单信息子行（1 行或多行）
日期行
colli 行（项目结束标志）

```

示例（6275 模板）：

```

010 4410441020 ECAS-Pressure Sensor, CVDE CN 39EA
11050926-00 2301400308HZ00(04.24 115797118
30.01.2026
colli: 174151807 39 EA

```

---

### 3️⃣ 项目边界规则（核心）

- ✅ **一个项目从 ITEM 行开始**
- ✅ **遇到 `colli` 行立即结束当前项目**
- ❌ `colli` 之后的内容（包装号、银行账号、页脚）一律不参与项目解析

这条规则用于避免：
- 把包装号当成订单号
- 把银行账号当成零件号
- 把页脚污染项目数据

---

### 4️⃣ 项目主行字段解析规则

#### 表头语义

```

项目号 | 零件号 | 名字 | Country of origin | 数量

```

#### 实现规则

- **数量**：匹配 `\d+EA`
- **国家**：匹配任意 `\b[A-Z]{2}\b`（CN / DE / TR / …）
- **名字**：
  - 优先：零件号之后 → 国家之前
  - fallback：零件号之后 → EA 之前

✅ 国家不写死  
✅ 名字不再包含 CN / DE 等国家码  

---

### 5️⃣ 订单信息解析（最复杂、最关键）

订单信息存在多种真实形态：

#### ✅ 表格对齐（多空格）

```

11050926-00    2301400308HZ00(04.24    115797118

```

#### ✅ 单空格压缩（6275）

```

11050926-00 2301400308HZ00(04.24 115797118

```

#### ✅ 两字段结构

```

LSDY-2026-4-10 115871821

```

---

#### ✅ 统一解析策略

1. **在项目子区块内持续扫描，直到拿到 `Our Order No.`**
2. 优先使用 **多空格分列**
3. fallback：整行扫描 ≥6 位数字
4. **从右向左识别**：
   - 最右侧 ≥6 位纯数字 → `Our Order No.`
   - 左侧依次回填：
     - `贵方订单号`
     - `贵方零件号`

---

### 6️⃣ 文本清洗策略

所有字段在写入 JSON 前都会经过统一清洗：

- `&nbsp;` / `\xa0` → 普通空格
- 多空格压缩
- 首尾空格去除

示例：

```

Clutch Servo \_AM  CN
→ Clutch Servo \_AM

````

---

## 🐞 Debug / Trace 模式

### 启用方式

```python
parser = DeliveryNoteParser(path, config, debug=True)
````

### 示例输出

```text
[TRACE] 项目 010：订单号 115797118 来自第 2 行（单空格 fallback）
[TRACE] 项目 010：遇到 colli，结束项目扫描
```

用途：

*   快速定位订单来源
*   回归测试验证解析路径
*   新模板调试

***

## 📌 已验证模板

*   ✅ 标准 SAP 表格模板
*   ✅ 多页 Delivery Note
*   ✅ 6275（单空格压缩订单行）
*   ✅ 78196275（多行订单 + colli 边界）
*   ✅ 索赔 / 免费订单
*   ✅ 中英文混合名称

***

## 🧪 建议回归用例

*   6275（单空格订单行）
*   78196275（多行订单 + colli）
*   77535479（三字段订单）
*   正常单页 / 多页 Delivery Note

***

## 🏁 总结

> **这是一个“结构驱动 + 语义兜底”的解析器。**  
> 不追求模板完全一致，而依赖稳定的结构事实：
>
> *   项目以 ITEM 开始
> *   项目以 colli 结束
> *   Our Order No. 永远是纯数字

***

## 📬 后续可扩展方向

*   抽象 `ItemBlockParser` 类
*   输出 `Country of origin` 字段
*   单元测试（pytest）
*   Debug 输出切换为 `logging`

***

**Author**: Pierre  
**Status**: Production-ready ✅

```

