# cad-drawing skill 安装说明（给同事）

一套机械零件 CAD 出图工作流：按模板风格画 AutoCAD 二维图纸、生成 STEP 三维模型
与 SolidWorks 参数化宏，并内置参数核查——你报的尺寸严格执行，发现矛盾/不合理/缺参数会先问再做。

---

## 方式一：项目级安装（推荐，团队共享一次到位）

把整个 `cad-drawing` 目录放进**团队项目的 `.workbuddy/skills/`** 下，随代码一起提交：

```
<项目目录>/
└── .workbuddy/
    └── skills/
        └── cad-drawing/
            ├── SKILL.md
            ├── INSTALL.md
            ├── references/
            └── scripts/
```

效果：任何人在该项目目录下打开 WorkBuddy 干活，都会自动加载这个 skill，
**不需要各自手工安装**，而且后续更新只要提交一次，全员同步。

适合场景：同一个团队、共用一批图纸模板和厂标。

---

## 方式二：用户级安装（个人跨项目可用）

解压后把 `cad-drawing` 目录放到自己的用户 skills 目录：

| 系统 | 路径 |
|---|---|
| Windows | `C:\Users\<你的用户名>\.workbuddy\skills\` |
| macOS | `~/.workbuddy/skills/` |

放好后应是 `...\.workbuddy\skills\cad-drawing\SKILL.md`。**必须重启/新开一次 WorkBuddy 会话**才会加载。

---

## 安装后必做：两步自检

### 1. 装 Python 依赖

在 `scripts/` 目录下执行（用你 WorkBuddy 的 Python，不需要管理员权限）：

```bat
python scripts/install_deps.py
```

只二维出图的话这就够了。要生成三维模型/STEP，加 `--full`（会装 cadquery，较慢）：

```bat
python scripts/install_deps.py --full
```

只想看看缺什么、不装：`python scripts/install_deps.py --check`

> cadquery 必须配 `cadquery-ocp==8.0.1.1.0`，版本不匹配会报
> `cannot import name 'TColgp_HArray1OfPnt' from 'OCP.TColgp'`。脚本已固定版本，别手动改。

### 2. 自检 CAD 连接

```bat
python scripts/_acad.py
```

正常会打印类似：

```
当前 Python: C:\...\python.exe
已连接 AutoCAD: AutoCAD.Application.24.2 (≈ 2023 版)
AutoCAD 文档数: 0
已连接 SolidWorks: SldWorks.Application.31 | 版本: ...
```

**连不上 AutoCAD 的排查顺序**：

1. 装的是不是完整版 AutoCAD？DWG TrueView、eDrawings、AutoCAD LT 都**没有 COM 接口**
2. 手动启动一次 AutoCAD 再重试（COM 服务需首次注册）
3. 版本特殊时显式指定 ProgID：
   ```bat
   set CAD_AUTOCAD_PROGID=AutoCAD.Application.24.3
   ```
   版本号对照见 `references/autocad-com.md`

---

## 关于路径，你什么都不用改

这个 skill 里**没有写死任何机器专属路径**：

- Python 用当前解释器，不含用户名
- AutoCAD 的 COM ProgID 自动探测，2018～2026 都能连
- 打印设备名、纸张名都有回退逻辑

如果你在自己的机器上发现某处路径失效，那是 bug，请反馈而不是手工改死。

---

## 目录里都有什么

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 主规范：4 条铁律 + 6 阶段工作流 + 踩坑速查 |
| `references/param-review.md` | **参数核查清单**：矛盾检测规则、必填项、提问模板 |
| `references/autocad-com.md` | AutoCAD COM 配方与坑位 |
| `references/dxf-authoring.md` | ezdxf 出图规范：字体、图层、剖面线、标注 |
| `references/factory-standard.md` | 厂标：图框坐标、标题栏栏目原文、视图标注习惯 |
| `scripts/_acad.py` | CAD 环境探测（先跑它自检） |
| `scripts/install_deps.py` | 依赖安装 |
| `scripts/dwg_to_dxf.py` | DWG → DXF（安全副本，不碰原文件） |
| `scripts/plot_pdf.py` | 让 AutoCAD 自己打印 PDF（预览的正解） |
| `scripts/verify_plot.py` | 出图自检：页面尺寸、内容边界、着墨率 |
