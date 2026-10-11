# -*- coding: utf-8 -*-
"""
VBScript / VBA 源码转码 + 词法自检  (给 cad-drawing skill 用)

为什么需要这个脚本
------------------
WScript.exe 读 .vbs 的规则是：
    带 BOM（UTF-16 LE/BE） -> 按 Unicode 解析
    不带 BOM               -> 按系统 ANSI 代码页解析（中文系统 = GBK/936）

所以把带中文注释的 .vbs 存成 UTF-8 无 BOM，wscript 会拿 GBK 去拆 UTF-8 字节，
注释里紧跟在中文后面的 `'` 会被当作双字节字符的第 2 字节吞掉，
引号配对错乱，编译期报「未结束的字符串常量」（800A0409），
而且报出的行号往往是空行，极易误判成脚本逻辑错误。

VBA 编辑器则相反：「文件 > 导入文件」按系统 ANSI 读 .bas，UTF-8 会乱码。

用法
----
    # .vbs -> UTF-16 LE + BOM + CRLF（双击 / cscript 运行）
    python vbs_encode.py 源码.txt 输出.vbs

    # .bas -> ANSI/GBK + CRLF（VBA 编辑器导入）
    python vbs_encode.py 源码.txt 输出.bas --gbk

输入文件应当是 UTF-8 编码的源码（可直接用 Write 工具写出来）。
脚本只做转码与静态检查，不会执行任何代码。
"""
import argparse
import io
import os
import re
import sys


def strip_line(raw):
    """返回 (代码部分, 该行结束时是否仍处于未闭合字符串)。"""
    state = "code"
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if state == "code":
            if c == '"':
                state = "str"
            elif c == "'":
                break                       # 注释开始
            else:
                out.append(c)
        else:                               # 字符串内
            if c == '"':
                if i + 1 < n and raw[i + 1] == '"':
                    i += 2
                    continue                # "" 是转义的双引号
                state = "code"
        i += 1
    return "".join(out), state == "str"


def check(text):
    """静态检查，返回问题列表。"""
    problems = []
    all_code = []
    for no, raw in enumerate(text.split("\n"), 1):
        s = raw.rstrip()
        code, unterminated = strip_line(s)
        all_code.append(code)

        if unterminated:
            problems.append(f"第 {no} 行：字符串未闭合 -> {s!r}")

        if s.endswith("_"):
            if not s[:-1].endswith((" ", "\t")):
                problems.append(f"第 {no} 行：续行符 '_' 前缺空格 -> {s!r}")

        # 无括号调用 + 参数以负号开头：有被解析成减法的歧义风险
        c = code.strip()
        if re.match(r"^(?:Call\s+)?(?:[A-Za-z_]\w*|\w+\.\w+)\s+-\S", c):
            if not c.startswith(("If ", "For ", "Do ", "Else", "End ", "On ")):
                problems.append(
                    f"第 {no} 行：参数以负号开头，建议先算入变量 -> {s!r}")

    joined = "".join(all_code)
    if joined.count("(") != joined.count(")"):
        problems.append(
            f"全文括号不配对：'(' x{joined.count('(')}  ')' x{joined.count(')')}")

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="UTF-8 源码文件")
    ap.add_argument("dst", help="输出文件（.vbs 或 .bas）")
    ap.add_argument("--gbk", action="store_true",
                    help="输出 ANSI/GBK 而不是 UTF-16 LE（.bas 用）")
    args = ap.parse_args()

    text = io.open(args.src, encoding="utf-8").read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    print("=== 词法自检 ===")
    problems = check(text)
    if problems:
        print("\n".join("  " + p for p in problems))
        print(f"共 {len(problems)} 处问题，未写盘")
        return 1
    print("  引号 / 续行符 / 括号 / 负号参数 全部正常")

    data = text.replace("\n", "\r\n")

    if args.gbk:
        try:
            payload = data.encode("gbk")
        except UnicodeEncodeError as e:
            ch = data[e.start:e.end]
            print(f"!! GBK 无法编码字符 {ch!r} (U+{ord(ch[0]):04X})，"
                  f"请把它换成全角/中文标点或删除")
            return 1
        with io.open(args.dst, "wb") as f:
            f.write(payload)
        kind = "ANSI/GBK"
    else:
        with io.open(args.dst, "wb") as f:
            f.write(b"\xff\xfe")                    # UTF-16 LE BOM
            f.write(data.encode("utf-16-le"))
        kind = "UTF-16 LE + BOM"

    size = os.path.getsize(args.dst)
    print(f"\n已写出: {args.dst}")
    print(f"编码: {kind} + CRLF    大小: {size} bytes")

    # 回读验证
    raw = io.open(args.dst, "rb").read()
    if args.gbk:
        ok = raw[:2] not in (b"\xff\xfe", b"\xfe\xff") and raw[:3] != b"\xef\xbb\xbf"
        back = raw.decode("gbk")
    else:
        ok = raw[:2] == b"\xff\xfe"
        back = raw[2:].decode("utf-16-le")
    print("编码校验:", "OK" if ok else "!! 异常")
    print("回读行数:", back.count("\r\n") + 1)
    print("回读首行:", back.split("\r\n")[0][:50])
    return 0


if __name__ == "__main__":
    sys.exit(main())
