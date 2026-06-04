# OCR 字体放大算法 — 设计文档

## 概述

在现有 split 分页算法基础上，新增 OCR 模式：用 PaddleOCR 检测图片中的文字位置和内容，擦除原文后用更大字号重绘，繁体自动转简体。

## 处理流程

### Split 模式（现有，不变）

```
原图 → 水平中线裁成上下两半 → 各旋转90° → 缩放到填满目标尺寸 → 输出
```

### OCR 模式（新增）

```
原图 (W×H)
  │
  ├─ PaddleOCR 检测 → [(文字, bbox, 置信度), ...]
  │
  ├─ 繁→简转换    → zhconv 将繁体转为简体
  │
  ├─ 擦除原文     → 取 bbox 外围像素均值色填充
  │
  └─ 放大重绘     → 用简体文字 + 原字号×font_scale 重新渲染
  │
   输出图 (W×H)
```

输出：原图 + OCR 放大后图片（2 张图，后缀 `_OCR`），图片尺寸不变。

## 模块架构

```
cli.py                    + --mode {split,ocr}   + --font-scale <float>
epub_processor.py         根据 mode 分派到不同处理函数
image_processor.py        现有：split + rotate + scale_to_fill（不变）
ocr_processor.py          新增：detect → convert → erase → render
```

### 新增依赖

| 包 | 用途 | 安装方式 |
|----|------|----------|
| `paddlepaddle` | PaddlePaddle 推理框架 | pip |
| `paddleocr` | OCR 检测+识别 | pip |
| `zhconv` | 繁简中文转换 | pip |

## CLI 接口

```
epub-reformat -i <dir> -o <dir> [--mode {split,ocr}] [--font-scale <float>] [-q <quality>] [-v]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 处理算法：`split` / `ocr` | `split` |
| `--font-scale` | OCR 模式下字体放大倍数 | `1.5` |
| `-q` / `--quality` | JPEG 输出质量 (1-100)，两种模式均生效 | `95` |
| `-v` / `--verbose` | 详细日志 | False |

## OCR 算法细节

### 文字检测

- 调用 PaddleOCR 获取每行文字的 bbox (x1,y1,x2,y2)、文本内容、置信度
- 置信度 < 0.5 的文字跳过，不处理
- 未检测到任何有效文字 → 保留原图不变

### 繁简转换

- 使用 `zhconv.convert(text, "zh-cn")` 逐条转换
- 已是简体的文字不受影响

### 擦除原文

- 对每个 bbox，向外扩展 2px 取一圈像素
- 计算该圈像素的均值色
- 用该颜色填充整个 bbox 区域（略扩展 1px 边距）

### 字号估算与重绘

- 原字号 = bbox 高度
- 新字号 = round(bbox_height × font_scale)
- 使用 PIL ImageDraw.text() 渲染
- 中文字体：自动查找系统字体（`/usr/share/fonts/`），找不到则报错
- 文字颜色：取原 bbox 内部像素的均值色（保留原文字颜色）
- 文字在 bbox 内居中，若放大后超出 bbox 边界则向右/下扩展

## 错误处理

沿袭现有逐层容错策略，新增 OCR 模式特定场景：

| 场景 | 行为 |
|------|------|
| 未检测到任何文字 | 保留原图 |
| 单条置信度 < 0.5 | 跳过该条 |
| PaddleOCR 模型加载 | 启动时预加载，输出提示 |
| 找不到中文字体 | 报错退出，提示安装字体 |
| 图片损坏/极小 | 沿用现有逻辑，保留原图 |

## 测试策略

### 单元测试 `tests/test_ocr_processor.py`

- 白底+黑色中文文字图片 → 验证 OCR 检测到文字
- 验证擦除后 bbox 区域像素改变
- 验证重绘后字号大于原字号
- 繁体输入 → 验证输出简体
- 无文字图片 → 验证保留原图
- OCR 模式返回原图 + OCR 处理图（长度 = 2）

### 集成测试 `tests/test_integration.py`

- 新增 `--mode ocr` 端到端测试：含文字 EPUB 经过处理后输出合法 EPUB，图片尺寸不变
- 现有 split 模式测试不受影响
