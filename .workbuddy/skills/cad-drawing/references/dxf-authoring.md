# ezdxf 出图规范

生成 R2010（AutoCAD 2018 可直接打开，也可另存 DWG）。

---

## 一、字体（中文图纸最关键的一环）

### 必须这样做

```python
doc = ezdxf.new("R2010", setup=True)
doc.header["$INSUNITS"] = 4          # 4 = 毫米

# 中文样式：国标 SHX 双字体
doc.styles.add("HZ", font="gbenor.shx", dxfattribs={"bigfont": "gbcbig.shx"})

# Standard 也要补上，否则默认样式不含中文
_std = doc.styles.get("Standard")
_std.dxf.font = "gbenor.shx"
_std.dxf.bigfont = "gbcbig.shx"
```

- `gbenor.shx` = 国标西文（数字/字母），`gbcbig.shx` = 大字体（汉字）
- 两者 AutoCAD 中文版自带，已确认存在于 `E:\AutoCAD\AutoCAD 2018\Fonts\`
- **不要用 `simsun.ttc`** —— TrueType 字体集合，AutoCAD 支持极差，会回退到无中文字形的 SHX，
  结果每个汉字显示成一个 `?`

### 清理多余样式

`ezdxf.new(setup=True)` 会自动塞入 20+ 个 OpenSans / Liberation 样式，都指向 AutoCAD 找不到的 .ttf，
打开时可能弹"未找到字体"对话框：

```python
for name in [s.dxf.name for s in doc.styles]:
    if name not in ("Standard", "HZ"):
        doc.styles.remove(name)
for name in [d.dxf.name for d in doc.dimstyles]:
    if name not in ("Standard", "GB"):
        doc.dimstyles.remove(name)
```

### 代码页

ezdxf 对 R2010 固定写 `ANSI_1252`（西欧）。保存后做字节替换：

```python
doc.saveas(path)
raw = open(path, "rb").read().replace(b"ANSI_1252", b"ANSI_936")
open(path, "wb").write(raw)
```

`ANSI_936` 是简体中文图纸惯例，避免第三方读取器误判编码。

---

## 二、图层与线宽

按用途分层，线宽用**百分之一毫米**整数（GB 机械图常用两档）：

| 图层 | 线宽 | 用途 |
|---|---|---|
| FRAME | 50 (0.50mm) | 图框、标题栏 |
| OUTLINE | 50 (0.50mm) | 零件可见轮廓 |
| THIN | 25 (0.25mm) | 尺寸线、剖面线外的细线 |
| HATCH | 13 (0.13mm) | 剖面线 |
| CENTER | 25 (0.25mm) | 中心线（点划线） |
| HIDDEN | 25 (0.25mm) | 隐藏线 |
| TEXT | 25 (0.25mm) | 文字 |
| DIM | 25 (0.25mm) | 标注 |

```python
doc.layers.add("OUTLINE", color=7, lineweight=50)
```

颜色一律用 7（白/黑），靠**线宽**分级，配合 `monochrome` 打印样式才不会出错。

---

## 三、剖面线

- **金属**：45° 单向细实线
- **玻璃/绝缘材料**：45° + 135° 交叉网纹（GB 规定的非金属/绝缘材料表示法）

线间距在 1:1 图纸上取 2–3mm，放大图里按视觉密度调整，不要糊成一片。

---

## 四、标注

```python
dim = msp.add_linear_dim(
    base=(x, y),
    p1=(x1, y1), p2=(x2, y2),
    dimstyle="GB",
    override={"dimtxsty": "HZ"},    # 标注文字也要用中文样式
)
dim.render()
```

- 直径符号用 `φ`（U+03C6），写成 `φ1.6` 而非 `%%c1.6`
- 标注样式 `GB` 的 `dimtxsty` 必须指向中文样式，否则标注里的中文会出问题

---

## 五、预览渲染（重要：不要在这里翻车）

### ✗ 错误做法

```python
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(msp, finalize=True)
```

matplotlib **不认识 SHX 字体**，会把每个汉字渲染成空心方框（tofu）。
用户看到的就是"PDF 里文字全是一个个框"，而 DXF 本身完全正常。

### ✓ 正确做法

让 AutoCAD 自己打印 PDF，再用 PyMuPDF 转 PNG：

```python
# 1. COM 打印（见 references/autocad-com.md 与 scripts/plot_pdf.py）
# 2. PDF → PNG
import pymupdf
pix = pymupdf.open(pdf)[0].get_pixmap(dpi=300)
pix.save(png)
```

### 若必须走 matplotlib（仅作兜底）

`MatplotlibBackend` 会按内容宽高比重设 figure 尺寸，竖版 A4 会被压成 101.6×159.7mm。
必须在 `draw_layout` 之后强制校正：

```python
ax.set_xlim(0, 210); ax.set_ylim(0, 297)
ax.set_aspect("equal")
fig.set_size_inches(210/25.4, 297/25.4)
```

且仍无法解决中文方框问题——**兜底方案只能用于核对几何，不能作为交付预览**。

---

## 六、自检

生成 DXF 后回读检查：

```python
d = ezdxf.readfile(path)
print(d.dxfversion, d.header.get("$DWGCODEPAGE"))
print([(s.dxf.name, s.dxf.get("font"), s.dxf.get("bigfont", "")) for s in d.styles])
aud = d.audit()
print("错误数:", len(aud.errors), "修复数:", len(aud.fixes))
```

- 样式表应只剩 `Standard` / `HZ`
- 代码页应为 `ANSI_936`
- `audit()` 应为 0 错误

再核对图元范围是否落在图框内、关键线段坐标是否等于理论值（如 φ0.5×10:1 = 5mm 宽）。
