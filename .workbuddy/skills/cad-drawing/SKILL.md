---
name: cad-drawing
description: 机械零件 CAD 出图工作流——AutoCAD 二维图纸（DXF/DWG）、SolidWorks 三维模型与参数化宏、STEP 交换文件。当用户要求画零件图、按已有模板改图出新规格、生成或导出 DXF/DWG/STEP、编写 SolidWorks 建模宏，或提供 STEP/DWG/PDF 模板要求"照这个风格画"时使用。内置参数核查协议：严格执行用户给定的尺寸，主动发现几何矛盾、不合理处与缺失参数并立即询问确认。
agent_created: true
---

# 机械零件 CAD 出图

面向机械零件（连接器、玻璃封接件、轴套类回转体等）的完整出图流程：参数确认 → 模板风格提取 → 二维图纸 → 三维模型 → 预览校验。

### 环境要求（每台机器会自动探测，不要写死路径）

- **AutoCAD**（必需，要有 COM 接口；DWG TrueView / eDrawings 不算）
- **SolidWorks**（仅三维建模/宏时需要）
- Python 包：`ezdxf` `pymupdf` `pywin32` `numpy` `pillow` `matplotlib`（预览校验用）、
  `cadquery==2.8.0` + `cadquery-ocp==8.0.1.1.0`（三维建模用）

**路径与版本一律不写死**：

- Python 用当前解释器 `sys.executable`，不要写 `C:\Users\<某人>\...`
- AutoCAD 的 COM ProgID 带版本号（2018=`.22`、2023=`.24.2`、2024=`.24.3`…），
  用 `scripts/_acad.py` 的 `connect_autocad()` 自动探测，详见 `references/autocad-com.md`
- 首次在新机器运行时，先跑 `python scripts/_acad.py` 自检，它会打印探测到的版本与当前文档数

---

## 铁律（优先级高于一切效率考虑）

### 铁律 1：参数严格执行，禁止"合理推测"

用户报出的每一个尺寸都是硬约束。禁止出现以下行为：

- 觉得某个尺寸"不合理"就自行改成自认为合理的值
- 用"行业惯例"覆盖用户明确给出的数值
- 把用户没说清楚的数字靠脑补填进图纸

拿不准就是拿不准，**问**。宁可多问一轮，不可画错一批。

### 铁律 2：发现矛盾、不合理、缺参数，立即询问

出图前必须对参数做一次完整核查（清单见 `references/param-review.md`）。命中以下任一类，停下来问用户：

| 类别 | 典型情况 | 例子 |
|---|---|---|
| **几何矛盾** | 尺寸之间在数学上无法共存 | 孔 φ0.45 却要装 φ0.5 的轴；壁厚 ≤ 0；各分段之和 ≠ 总长；定位尺寸超出总长 |
| **不合理** | 能画出来但工艺/功能上站不住 | 玻璃环壁厚 0.35mm 且高 1.6mm 偏薄；比例选得图框装不下；公差等级与工艺能力不匹配 |
| **缺参数** | 图纸必需但用户没给 | 材料、比例、未注公差、表面粗糙度、倒角、数量、图号命名规则、标题栏填写内容 |

提问方式：
- 用 `AskUserQuestion`，**一次性问题组**不超过 4 个，避免挤牙膏式反复打断
- 每个选项给明确后果描述，把推荐项放第一个并标注
- 缺失项很多时，先问影响几何的那些；标注/文字类可先按模板惯例填，并在交付时列出来让用户复核

**不要**因为看起来"小"就跳过。图号写错、明细栏规格对不上，返工成本远高于多问一句。

### 铁律 3：参数冲突时以最后一次明确指令为准，并列出被覆盖项

用户改口是常态。处理方式：

1. 以**最后一条明确指令**为准
2. 出图时明确列出"哪些参数被覆盖、原值是什么、现值是什么"
3. 若新旧指令仍有无法调和之处，回到铁律 2 提问

例：用户先说"中心孔距 0.45"、后又说"忽略我说的 0.45，按内导体 φ0.5×长 12 画" —— 按后者执行，并在交付说明里写清 0.45 已被忽略。

### 铁律 4：不碰用户的 CAD 会话与原始文件

- **绝不**调用 `acad.Quit()` —— 连接的往往是用户正在运行的实例，里面有他没保存的图
- 需读用户 DWG 时，**先复制到工作目录**再打开，原文件只读
- **只关闭自己打开的那一个文档对象**（持有 `doc` 引用直接 `doc.Close(False)`），
  **绝不按文件名遍历** `Documents` 去匹配关闭 —— 名字可能重复，会误关用户的图
- 操作前后各读一次 `acad.Documents.Count`，**数量不一致必须明确告警**并请用户检查
- 成果落在工作区 `output/`，不覆盖模板目录

已知风险：用户可能在脚本运行期间手动关闭图纸，导致持有的 COM 文档对象失效，
`Close` 抛 `被调用的对象已与其客户端断开连接`。此时不要重试、不要遍历兜底，
直接报告"文档数发生变化，请检查 AutoCAD"。脚本已按此实现。

---

## 工作流

### 阶段 1：参数确认

1. 把用户给的参数整理成表逐条列出，回读一遍
2. 按 `references/param-review.md` 做矛盾与缺失项核查
3. 有疑问用 `AskUserQuestion` 一次性问清
4. **确认后再动手**。不要边问边画、画一半再改

### 阶段 2：找模板

优先找用户单位已有的同类图纸作风格基准（主动问"有没有现成的同类图纸"）。有的话：

- **DWG** → 用 `scripts/dwg_to_dxf.py` 转 DXF，再用 ezdxf 读文字（标题栏真实措辞、明细栏规格）
- **STEP** → 用 OCP/cadquery 读实体，算体积与包围盒，反推几何参数并与用户报的值交叉验证
- **PDF** → 用 PyMuPDF 矢量化提取图框网格、标注箭头位置、剖面线角度；**文字通常已转曲，读不出内容**

三者互相印证：STEP 验几何、DWG 验文字、PDF 验排版。

### 阶段 3：生成二维图纸（DXF）

用 ezdxf 生成 R2010。规范见 `references/dxf-authoring.md`，三条硬要求：

1. 中文必须用 **SHX 双字体**：`gbenor.shx` + 大字体 `gbcbig.shx`（AutoCAD 中文版自带）
2. 清掉 `ezdxf.new(setup=True)` 自动塞入的 OpenSans/Liberation 样式，只留必要样式
3. 保存后做字节替换，把 `$DWGCODEPAGE` 的 `ANSI_1252` 改成 `ANSI_936`

### 阶段 4：三维模型与 SolidWorks 宏

- STEP 用 cadquery 生成（必须配 `cadquery-ocp==8.0.1.1.0` + `cadquery==2.8.0`）
- 生成后**必须**打印每个实体的体积与包围盒，与理论值对照，确认定位关系正确
- SolidWorks VBA/VBS 宏：API 长度单位是**米**，mm 值需 ×0.001；参数集中在文件顶部常量区
- **宏必须先在 Python 里实跑一遍 API 序列再落成 VBS**（见 `references/solidworks-com.md`）。
  不要照抄旧宏骨架改参数就交付 —— 实测旧宏骨架漏掉 `AddToDB` 会导致
  三次拉伸全部失败、一个实体都建不出来，而报错信息完全看不出原因。
  实跑校验的做法：新建零件 → 逐步建模 → 打印实体数/体积/包围盒 → 与解析解对照 →
  只关闭自己新建的文档，绝不 `Quit`。
- **交付宏文件前必须过一遍 `scripts/vbs_encode.py`**（转码 + 词法自检）。
  `.vbs` 必须存成 **UTF-16 LE + BOM**；UTF-8 无 BOM 会让 WScript 按 GBK 拆错字节，
  双击时报「未结束的字符串常量」，且报出的行号往往是空行，极易误判：
  ```bash
  python scripts/vbs_encode.py 源码.txt 输出.vbs          # .vbs -> UTF-16 LE + BOM
  python scripts/vbs_encode.py 源码.txt 输出.bas --gbk    # .bas -> ANSI/GBK
  ```

### 阶段 5：出 PDF 预览 —— 必须让 AutoCAD 自己打印

**禁止用 matplotlib 渲染 DXF 生成预览 PDF/PNG。** matplotlib 不认识 SHX 字体，会把每个汉字画成一个空心方框（tofu），用户看到的就是"文字全是一个个框"。

正确做法：用 `scripts/plot_pdf.py` 通过 COM 让 AutoCAD 打印，预览即 AutoCAD 真实输出。关键点：

- 纸张选 **full_bleed** 无边距规格，否则 1:1 对不齐
- **先** `SetWindowToPlot()` **再** `PlotType = 4`（顺序反了报"输入无效"）
- 打完再用 PyMuPDF 从该 PDF 渲染 PNG

配方见 `references/autocad-com.md`。

### 阶段 6：验证与交付

1. `scripts/verify_plot.py` 校验打印结果：页面尺寸、内容边界、着墨率
2. **裁局部放大图用 Read 工具肉眼核对**（本机 Read 能读图片）—— 标题栏文字、关键剖面各看一眼
3. 交付时说明：最终采用的参数表、被覆盖的旧参数、仍需用户确认的遗留项

---

## 参考资源

| 文件 | 内容 |
|---|---|
| `references/param-review.md` | **参数核查清单**：矛盾检测规则、机械图必填项、提问模板 |
| `references/autocad-com.md` | AutoCAD COM 配方：DWG→DXF、打印 PDF、已踩过的坑 |
| `references/solidworks-com.md` | **SolidWorks COM 建模踩坑实录**：`AddToDB`、圆弧方向、`SaveAs3` 返回值、模板兜底、属性/方法辨析、`.vbs` 编码坑、`.vbs` 与 `.swb` 跑法差异 |
| `references/dxf-authoring.md` | ezdxf 出图规范：字体、图层、样式、剖面线、标注 |
| `references/factory-standard.md` | 南京广兆测控技术有限公司厂标（图框、标题栏栏目与坐标） |
| `scripts/_acad.py` | **CAD 环境探测**：自动找本机 AutoCAD/SolidWorks 版本，换机器先跑它 |
| `scripts/install_deps.py` | 依赖自检与安装（`--check` 只检查、`--full` 含三维建模） |
| `scripts/dwg_to_dxf.py` | COM 把 DWG 另存为 DXF（安全复制 + 不退出 AutoCAD） |
| `scripts/plot_pdf.py` | COM 打印 DXF 为 PDF（1:1、无边距、窗口打印） |
| `scripts/verify_plot.py` | 校验打印 PDF 的页面尺寸、内容边界、着墨率 |
| `scripts/vbs_encode.py` | **宏文件转码 + 词法自检**：`.vbs`→UTF-16 LE、`.bas`→ANSI/GBK，并查引号/括号/续行符 |
| `INSTALL.md` | **分发给同事的安装说明**（项目级 / 用户级两种装法 + 自检步骤） |

---

## 换机器 / 分享给同事

本 skill 不含任何机器专属路径，可直接拷贝。三种分发方式：

1. **项目级（团队共享，推荐）** —— 放进项目 `.workbuddy/skills/cad-drawing/` 随代码提交，
   项目成员自动生效、更新只需提交一次
2. **用户级** —— 拷到各人 `~/.workbuddy/skills/`，需重开会话才加载
3. **打包分发** —— 把整个目录打成 zip，按 `INSTALL.md` 装

新机器上按顺序做两件事：`python scripts/install_deps.py` → `python scripts/_acad.py` 自检。
详见 `INSTALL.md`。

---

## 已知环境陷阱速查

| 现象 | 原因 | 处理 |
|---|---|---|
| AutoCAD 打开 DXF 中文全是 `?` | 样式用了 `simsun.ttc`，AutoCAD 不认 .ttc | 换 `gbenor.shx` + `gbcbig.shx` |
| 预览 PDF 中文是空心方框 | matplotlib 不认 SHX 字体 | 改用 AutoCAD 打印（`scripts/plot_pdf.py`） |
| 打印出来内容挤偏/被裁 | 用了带边距的普通 A4 | 换 `ISO_full_bleed_A4_(210.00_x_297.00_MM)` |
| `PlotType = 4` 报"输入无效" | 没先设窗口 | 先 `SetWindowToPlot()` 再设 `PlotType` |
| `import cadquery` 报缺 OCP | 版本不匹配 | 装 `cadquery-ocp==8.0.1.1.0` + `cadquery==2.8.0` |
| DWG 二进制扫不出文字 | AC1032 压缩格式 | 走 COM `SaveAs` 转 DXF |
| PDF 里文字识别不出 | 转曲了；SHX 字形与 TrueType 不同 | 从 DWG 读，别做 OCR |
| PyMuPDF 裁图裁错位置 | clip 坐标 y 向下，DXF y 向上 | 底部区域要写 `297 - y` |
| AutoCAD 拒绝打开 DXF，报"解密数据时出错" | 图层引用了 LTYPE 表里不存在的线型（如 `HIDDEN`） | 换 `DASHED`，生成前用线型表断言拦截 |
| SolidWorks 拉伸返回 Nothing、实体数 0 | 没开 `skMgr.AddToDB = True`，草图被自动几何关系篡改 | 建图元前 `AddToDB = True`，建完置回 False |
| SolidWorks 草图圆半径不对（变成到原点的距离） | 同上，圆被吸附到原点 | 同上 |
| SolidWorks 腰形两端变成内凹 | `CreateArc` 方向写成 `-1` | 方向必须是 `+1` |
| `SaveAs3` 判断成败误报失败 | 成功时返回 0，不是 True | 以文件是否落盘为准 |
| `NewDocument` 返回 Nothing | 注册表默认模板路径是过期的 | 兜底搜 `ProgramData\SolidWorks\*\templates\*.prtdot` |
| pywin32 报 `'int' object is not callable` | SW 的 `GetDocumentCount`/`GetTitle`/`FirstFeature` 等是**属性**不是方法 | 去掉括号，见 solidworks-com.md 第 7 节 |
| 双击 `.vbs` 报「未结束的字符串常量」(800A0409)，行号还是空行 | `.vbs` 存成了 UTF-8 无 BOM，WScript 按 GBK 拆错中文字节、吃掉引号 | 用 `scripts/vbs_encode.py` 转成 UTF-16 LE + BOM |
| SW「工具 > 宏 > 运行」里选不到 `.vbs` | 该对话框只认 `.swp`/`.swb` | `.vbs` 用双击跑；想进菜单用 `.bas` 粘进 VBA 编辑器再导出成 `.swb` |
