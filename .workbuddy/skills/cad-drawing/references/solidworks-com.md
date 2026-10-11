# SolidWorks COM 建模踩坑实录（本机 SW 2023 实测）

所有结论都在本机 SolidWorks 2023（`SldWorks.Application`，安装目录 `E:\SW2023`）实跑验证过。
**写宏之前必须通读，照抄旧宏骨架而不带这些要点，几乎必然失败。**

---

## 1. 头号坑：必须开 `SketchManager.AddToDB`

```vbs
skMgr.InsertSketch True
skMgr.AddToDB = True      ' ★ 建图元之前
' ... CreateLine / CreateArc / CreateCircleByRadius ...
skMgr.AddToDB = False
skMgr.InsertSketch True
```

不开会怎样（实测）：

| 草图内容 | 不开 AddToDB | 开 AddToDB |
|---|---|---|
| 单个圆 `x=-1.27, r=0.25` | 圆被吸附到原点，半径变成到原点的距离 → r=1.27 | 正确 r=0.25 |
| 三圆同草图 `-1.27/0/+1.27` | 只出 2 个体，其中一个 r=1.27 | 正确 3 个体 |
| 同心圆环（DC1616 的外导体/玻璃） | **三次拉伸全部返回 Nothing，实体数 0** | 正确 3 个体 |
| 腰形（2 直线 + 2 圆弧） | 拉伸返回 Nothing，实体数 0 | 正确 |

原因：自动几何关系/推理吸附会篡改草图图元，轮廓解不出来。

---

## 2. `CreateArc` 方向参数：`+1` 是逆时针，实测必须用它

`CreateArc(xc,yc,zc, x1,y1,z1, x2,y2,z2, Direction)`

腰形（跑道形）两端半圆，想要**向外凸**：

```vbs
skMgr.CreateLine -A, -R, 0,  A, -R, 0
skMgr.CreateArc   A, 0, 0,   A, -R, 0,   A,  R, 0,  1    ' 右端
skMgr.CreateLine  A,  R, 0, -A,  R, 0
skMgr.CreateArc  -A, 0, 0,  -A,  R, 0,  -A, -R, 0,  1    ' 左端
```

实测对照（4.29×1.5 腰形，厚 1.5）：

- `Direction = +1`：V = **8.9282**（= (2×1.395×1.5 + π×0.75²) × 1.5）✅
- `Direction = -1`：V = 3.6268 —— 两端变成**内凹**，是错的形状 ❌

判断方法：起点/终点相对圆心的夹角，沿指定方向走过的是哪半边。

---

## 3. `SaveAs3` 成功时返回 0，不能用 `= False` 判断

实测：文件确实写出来了，返回值却是 `0`。

```vbs
' ❌ 错：0 = False，会被误判成失败
If swModel.SaveAs3(sldprt, 0, 0) = False Then ...

' ✅ 对：以文件是否落盘为准
swModel.SaveAs3 sldprt, 0, 0
If Not fso.FileExists(sldprt) Then Die "保存失败"
swModel.SaveAs3 stepFile, 0, 2      ' 2 = 另存副本
```

---

## 4. 默认零件模板的注册表路径可能是过期的

`swApp.GetUserPreferenceStringValue(8)`（8 = swDefaultTemplatePart）返回
`C:\ProgramData\SolidWorks\SOLIDWORKS 2023\templates\零件.prtdot`，
**该文件不存在** → `NewDocument` 返回 Nothing。真实模板是 `gb_part.prtdot`。

兜底做法：注册表值不存在就遍历 `C:\ProgramData\SolidWorks\*\templates\*.prtdot` 取第一个。
（不要去改用户注册表里的默认模板设置。）

---

## 5. 单位是米，不是毫米

宏里统一写 `Const M = 0.001`，所有尺寸 `* M` 后传给 API。

---

## 6. 偏置起点：`FeatureExtrusion2` 的 T0 / StartOffset

```vbs
FeatureExtrusion2( _
    True, False, False, 0, 0, depth, 0, _          ' 单向、盲孔、深度
    False, False, False, False, 0, 0, _
    False, False, False, False, _                   ' 第 18 个 False = 不合并（多实体）
    False, True, True, t0, startOffset, False)      ' t0=3 (swStartOffset) + 偏置量
```

- `t0 = 0` 从草图面起；`startOffset > 0` 时 `t0 = 3`
- 第 18 个参数是 `Merge`：零件要多个独立实体就给 `False`
- 共 23 个参数，一个都不能少

---

## 7. pywin32 下很多「方法」其实是属性

用 Python 驱动时不要把下面这些当方法调用：

| 写成方法会报错 | 正确写法（属性） |
|---|---|
| `sw.GetDocumentCount()` | `sw.GetDocumentCount` |
| `model.GetTitle()` | `model.GetTitle` |
| `model.FirstFeature()` | `model.FirstFeature` |
| `f.GetTypeName2()` | `f.GetTypeName2` |
| `f.GetNextFeature()` | `f.GetNextFeature` |
| `sw.GetFirstDocument()` | `sw.GetFirstDocument` |
| `doc.GetNext()` | `doc.GetNext` |
| `model.EditRebuild3()` | `model.EditRebuild3`（访问即触发重建） |

真方法：`GetBodies2`、`GetBodyBox`、`GetMassProperties`、`SaveAs3`、`CloseDoc`、`EnumDocuments2`。

---

## 8. 「孔」要和外形画在同一个草图里，不要事后切除

三针排针：外导体 φ1.1 孔与内导体 φ0.5 同位置。若先建实体再切除，
φ1.1 的切除会把 φ0.5 的内导体**整根切掉**（针完全落在孔内）。

正确顺序：外导体（腰形 + 3 孔同草图一次成型）→ 内导体 → 玻璃环。

---

## 9. 安全守则

- **绝不调用 `swApp.Quit` / `ExitApp`** —— 用户可能开着 SolidWorks 在干活
- 运行前用 `GetFirstDocument/GetNext` 快照已有文档标题，结束时只关闭自己新建的
- 调试脚本要在开头清理上一次失败遗留的 `零件N` 空文档
- `swApp.Visible = True` 保持可见，别静默操作

---

## 10. 本机环境

| 项 | 值 |
|---|---|
| ProgID | `SldWorks.Application`（`SldWorks.Application.31` 也可） |
| 安装目录 | `E:\SW2023\SOLIDWORKS` |
| 真实零件模板 | `C:\ProgramData\SolidWorks\SOLIDWORKS 2023\templates\gb_part.prtdot` |
| 界面语言 | 中文简体（基准面名「前视基准面」，代码里用 `GetTypeName2 = "RefPlane"` 规避） |
| cscript/wscript | **本机沙箱禁止执行**（被当作 LOLBin 拦截），VBS 无法在本地实跑验证 —— 只能「先在 Python 里实跑验证 API 序列」+「用 `scripts/vbs_encode.py` 做编码与词法自检」+ 交付后请用户实跑反馈 |

---

## 11. 宏怎么跑：`.vbs` 与 `.swb`/`.swp` 是两回事

SolidWorks 的「工具 > 宏 > 运行」对话框**只认 `.swp` / `.swb`**，选不中 `.vbs`。
两种格式的跑法不同，别混：

| 文件 | 怎么跑 | 备注 |
|---|---|---|
| `.vbs`（独立 VBScript） | **资源管理器里双击**（wscript 跑），或 `cscript 文件.vbs` | 脚本自己 `CreateObject("SldWorks.Application")` 连 SW；不走 SW 菜单 |
| `.swb` / `.swp`（SW 宏工程） | 工具 > 宏 > 运行 选中它 | 在 SW 进程内运行，可用 `Application.SldWorks` 连当前实例 |

**想用 SW 宏菜单一键跑 `.vbs` 的逻辑**，两条路：
1. 把 `_可导入VBA.bas` 的内容粘进 SW 的 VBA 编辑器（工具 > 宏 > 新建 → 替换 Module1 桩），
   按 F5 运行；再「文件 > 导出」存成 `.swb`，以后就能在 Run 对话框里选到。
2. 或直接用「工具 > 宏 > 新建」从零写，把参数和 `Sub main()` 照抄即可。

> 注意：`.vbs` 用到 `WScript` 对象（取自身路径、退出），**不能原样粘进 SW VBA 编辑器**
> （VBA 里没有 `WScript`）。所以给 SW 菜单用的版本是独立的 `.bas`，已把 `WScript`
> 全部替换掉（退出改用 `End`，输出目录改用 `swModel.GetPathName` 的父目录 + 桌面兜底），
> 两者建模逻辑一致。

---

## 12. 【实测踩坑】`.vbs` 的编码错了会报「未结束的字符串常量」

这是真实发生过的一次翻车，报错信息**完全指向错误的方向**，记录在此。

双击 `.vbs` 弹出：

```
Windows Script Host
脚本: D:\...\DC-3P-0.5(8.8-0.8)_SolidWorks参数化建模宏.vbs
行:   48
字符: 72
错误: 未结束的字符串常量
代码: 800A0409
源:   Microsoft VBScript 编译器错误
```

看起来像脚本逻辑写错了，其实**跟逻辑无关，是文件编码**。而且报的第 48 行
可能是个**空行** —— 因为编码错乱后行内字节被吞，编译器算出的行号已经不可信。

根因：`WScript.exe` 读 `.vbs` 的规则是

- **带 BOM**（UTF-16 LE/BE）→ 按 Unicode 解析
- **不带 BOM** → 按**系统 ANSI 代码页**解析（中文系统 = GBK/936）

把 `.vbs` 存成 **UTF-8 无 BOM**（很多编辑器/写文件工具的默认行为）时，
wscript 会拿 GBK 去拆 UTF-8 的中文字节。GBK 是双字节编码，会把
「中文字节的第 2 个字节 + 紧随其后的 ASCII 字符」当成**一个**汉字吃掉；
注释里紧跟在中文后面的 `'` 被吞掉 → 引号配对错乱 → 编译器报「未结束的字符串常量」。

### 修复

```python
# 先把行尾统一成 CRLF，再写 UTF-16 LE + BOM
data = text.replace("\n", "\r\n")
with open(dst, "wb") as f:
    f.write(b"\xff\xfe")                  # UTF-16 LE BOM —— 关键
    f.write(data.encode("utf-16-le"))
```

三种编码的适用场合（别混）：

| 文件 | 该用什么编码 | 原因 |
|---|---|---|
| `.vbs` | **UTF-16 LE + BOM** ✅ | wscript 认 BOM；跨代码页，英文系统也不乱 |
| `.vbs` 备选 | ANSI / GBK ✅ | 中文系统能跑，但不跨代码页 |
| `.vbs` | **UTF-8 无 BOM** ❌ | 必坏，就是上面这个报错 |
| `.bas` | **ANSI / GBK** ✅ | VBA 编辑器「文件 > 导入文件」按系统 ANSI 读，UTF-8 会乱码 |

**写完 `.vbs` 一定要转码 + 自检**，用 `scripts/vbs_encode.py`（见下）：
它会把源文件转成 UTF-16 LE + BOM，并检查引号/续行符/括号配对、
以及「参数以负号开头」的可疑写法。

```bash
python scripts/vbs_encode.py 源文件.txt 目标.vbs          # .vbs -> UTF-16 LE
python scripts/vbs_encode.py 源文件.txt 目标.bas --gbk    # .bas -> ANSI/GBK
```

> 用记事本打开 `.vbs` 若显示正常，**不代表编码对**（记事本能自动猜 UTF-8）。
> 判断方法是看文件头两个字节是否为 `FF FE`（UTF-16 LE BOM）。

---

## 13. 无括号调用的参数别以负号开头

VBScript / VBA 里过程调用省略括号时，`过程名 -表达式` 存在被解析成
**减法运算**的歧义风险。写坐标时不要图省事：

```vbs
' ❌ 有歧义风险
skMgr.CreateLine -A * M, -R_END * M, 0,  A * M, -R_END * M, 0

' ✅ 先把负值算进变量，传参一律是简单变量
xL = 0 - A * M
xR = A * M
yU = R_END * M
yD = 0 - R_END * M
skMgr.CreateLine xL, yD, 0, xR, yD, 0
```

（此歧义未在实机确认会发生 —— 但本机无法运行 VBS 验证，按零风险写法写不值得省。）

