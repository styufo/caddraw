# AutoCAD COM 配方（2018 / Application.22 上实测，脚本已做版本自适应）

依赖 `pywin32`。Python 用当前解释器即可（`sys.executable`）——skill 脚本由 WorkBuddy
调用时，当前解释器就是已装好依赖的那个，**不要写死路径**（不同机器用户名不同）。

---

## 一、连接 —— 用 `scripts/_acad.py`，不要手写 ProgID

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _acad import connect_autocad

acad = connect_autocad()      # 自动探测本机版本，连不上抛 RuntimeError
```

**为什么不能写死 `AutoCAD.Application.22`**：ProgID 带版本号，各版本不同：

| 版本 | ProgID 后缀 | 版本 | ProgID 后缀 |
|---|---|---|---|
| 2018 | `.22` | 2023 | `.24.2` |
| 2019 | `.23` | 2024 | `.24.3` |
| 2020 | `.23.1` | 2025 | `.25` |
| 2021 | `.24` | 2026 | `.25.1` |
| 2022 | `.24.1` | | |

不带版本号的 `AutoCAD.Application` 在多数机器上**未注册**，会失败。

探测顺序：环境变量 `CAD_AUTOCAD_PROGID` → 注册表枚举 `AutoCAD.Application.*`
取最高版本 → 兜底无版本号。特殊环境可显式指定：

```bat
set CAD_AUTOCAD_PROGID=AutoCAD.Application.24.3
```

其它注意点：

- `GetActiveObject` 在用户未启动 AutoCAD 时会抛 `MK_E_UNAVAILABLE (0x800401E3)`
- `Dispatch` 会自动启动或连接现有实例。**连接的往往是用户正在跑的那个** → 铁律 4
- 探测失败先让用户手动启动一次 AutoCAD（COM 服务需首次注册）
- 装了 DWG TrueView / eDrawings 不算，它们没有 COM 接口

## 二、DWG → DXF（为了读文字）

```python
doc = acad.Documents.Open(dxf_src)        # 先把用户 DWG 复制到工作目录
doc.SaveAs(out_dxf, 49)                   # 49 = ac2010_dxf
```

- **必须先复制再打开**，绝不直接开用户原文件
- SaveAs 后 AutoCAD 的当前文档会变成新文件名，关闭时按新名匹配
- 转换后当前文档名会变（如 `src.dxf`）

## 三、打印 PDF（预览的正解）

完整可运行脚本见 `scripts/plot_pdf.py`。关键步骤与坑：

```python
doc.SetVariable("BACKGROUNDPLOT", 0)      # ① 关后台打印，保证同步返回
lay = doc.ActiveLayout
lay.ConfigName = "DWG To PDF.pc3"
lay.RefreshPlotDeviceInfo()

# ② 纸张必须 full_bleed（无边距）
lay.CanonicalMediaName = "ISO_full_bleed_A4_(210.00_x_297.00_MM)"

lay.PaperUnits = 1                        # 1 = acMillimeters
lay.RefreshPlotDeviceInfo()

# ③ 顺序关键：先设窗口，再设 PlotType
lo = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0, 0.0])
hi = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [210.0, 297.0])
lay.SetWindowToPlot(lo, hi)
lay.PlotType = 4                          # 4 = acWindow

# ④ 1:1 —— 图纸 1 单位 = 1 mm
lay.UseStandardScale = False
lay.SetCustomScale(1.0, 1.0)
lay.CenterPlot = True
lay.PlotWithLineweights = True
lay.ScaleLineweights = False

doc.Regen(1)
doc.Plot.PlotToFile(pdf_path)
doc.Close(False)                          # ⑤ 只关自己开的这一个
```

### 坑位明细

| 坑 | 现象 | 对策 |
|---|---|---|
| 普通 A4 有边距 | 内容被挤偏/裁掉（实测 x5.6–204 / y17.8–279，应为 5–205 / 5–297） | 用 `ISO_full_bleed_A4_(210.00_x_297.00_MM)`；换后实测 4.6–205.2 / 4.7–296.1 |
| `PlotType=4` 报"输入无效" | 未先设窗口 | 先 `SetWindowToPlot()` |
| PlotType 枚举限制 | 3/4/5 在 Model 布局被拒（只接受 0/1/2） | 先设窗口后设 4 即可；图纸空间布局可设 5 |
| `PlotStyleSheet` 不可写 | `Property 'Item.PlotStyleSheet' can not be set` | 忽略，默认样式表已能把白线打黑 |
| `PDFOUT` 等临时布局残留 | 探测时新建的布局没清 | 用完删掉 |
| VARIANT 传数组 | 直接传 list 失败 | `win32com.client.VARIANT(pythoncom.VT_ARRAY\|VT_R8, [x,y])` |

### 可用纸张名（GetCanonicalMediaNames）

```
ISO_full_bleed_A4_(210.00_x_297.00_MM)   ← 竖版无边距，出图首选
ISO_full_bleed_A4_(297.00_x_210.00_MM)   ← 横版无边距
ISO_A4_(210.00_x_297.00_MM)              ← 带边距，慎用
```

## 四、accoreconsole 的坑

`E:\AutoCAD\AutoCAD 2018\accoreconsole.exe` 存在，但**实测走不通**：

- Git Bash 会把 `/i` 转义成路径参数 → 只打印用法
- PowerShell 调用后输出被吞，且脚本内 `-DXFOUT` 参数顺序稍有偏差就卡在等输入
- **优先走 COM**，accoreconsole 只作为最后的备选

## 五、PyMuPDF 坐标陷阱

PyMuPDF 的 `Rect` / clip 是**左上原点、y 向下**；而 DXF 与 PDF 内容坐标是 y 向上。

裁图纸底部（如标题栏 PDF y 5–61）：

```python
S = 25.4 / 72.0
clip = pymupdf.Rect(x0/S, (297-61)/S, x1/S, (297-5)/S)
pix = pg.get_pixmap(dpi=500, clip=clip)
```

写错会裁到页面顶部，得到一张看起来"布局不对"的图，容易误判成图纸本身有问题。

## 六、安全约束（复述铁律 4）

```
✗ acad.Quit()                     会关掉用户正在用的 AutoCAD
✓ doc.Close(False)                只关自己打开的文档
✓ 复制 DWG 到工作目录再 Open      原文件只读
✓ 操作前打印 acad.Documents.Count 确认不会误伤
```

## 七、收尾清单

打印任务结束后：
1. `doc.Close(False)` 关闭临时文档
2. 确认 `acad.Documents.Count` 回到操作前的数量
3. 清理工作目录里的临时脚本与中间图
4. 在交付说明里告知用户"曾在你的 AutoCAD 里打开过临时文档，已关闭"
