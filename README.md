# robogame
学校机器人比赛代码

---

## 附件：PDF 解析模块 / PDF Reader Module

支持从本地文件或上传（multipart/form-data）读取 PDF，逐页提取文本并返回结构化 JSON，包含页码、文本和元数据（标题、作者、创建时间）。遇到扫描版（图片型）PDF 时会给出友好提示。

### 依赖安装

```bash
pip install -r requirements.txt
# 开发/测试额外依赖
pip install -r requirements-dev.txt
```

### CLI 用法

```bash
# 解析 PDF，输出完整 JSON（含各页文本）
python app.py path/to/file.pdf

# 只输出元数据和警告，跳过页面文本
python app.py path/to/file.pdf --no-pages
```

**示例输出：**

```json
{
  "metadata": {
    "title": "My Document",
    "author": "Alice",
    "creation_date": "D:20240101120000",
    "num_pages": 2
  },
  "pages": [
    { "page": 1, "text": "第一页内容..." },
    { "page": 2, "text": "第二页内容..." }
  ],
  "warnings": []
}
```

> 扫描版 PDF（图片型，无可提取文字）时，`warnings` 字段会包含提示信息，建议使用 [ocrmypdf](https://ocrmypdf.readthedocs.io/) 或 Tesseract 先进行 OCR 处理。

### Flask API 用法

```bash
# 启动服务（默认端口 5000）
python app.py --serve
```

| 端点 | 方法 | 说明 |
|------|------|------|
| `/parse` | POST | 上传 PDF（multipart/form-data，字段名 `file`） |
| `/parse-url` | POST | 解析服务器本地路径（JSON body: `{"path": "/path/to/file.pdf"}`） |

**上传示例（curl）：**

```bash
curl -X POST http://localhost:5000/parse \
     -F "file=@/path/to/document.pdf"
```

**本地路径示例（curl）：**

```bash
curl -X POST http://localhost:5000/parse-url \
     -H "Content-Type: application/json" \
     -d '{"path": "/path/to/document.pdf"}'
```

### 运行测试

```bash
python -m pytest tests/ -v
```

### 文件结构

```
robogame/
├── app.py                  # Flask API + CLI 入口
├── pdf_parser/
│   ├── __init__.py
│   └── parser.py           # 核心解析逻辑
├── tests/
│   └── test_pdf_parser.py  # 测试用例
├── requirements.txt        # 运行依赖
└── requirements-dev.txt    # 测试依赖
```
