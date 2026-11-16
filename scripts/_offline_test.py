# -*- coding: utf-8 -*-
"""离线单测: 用实测抓到的真实 HTML 片段验证解析正则。不联网。"""
import importlib.util, os, sys

spec = importlib.util.spec_from_file_location(
    "zl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "查资料.py"))
zl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zl)

ok = fail = 0


def chk(label, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("  [PASS] %s" % label)
    else:
        fail += 1
        print("  [FAIL] %s\n         got =%r\n         want=%r" % (label, got, want))


# ---------- 形态 A: 多文件列表(真实抓取片段,含 href 前后空格换行) ----------
HTML_A = '''<TR class="table-margin-alternation-td">
    <TD class="common indentten"><img alt="" src="/meol/common/icons/pdf.gif">&nbsp;

        <a  href="

            /meol/common/script/preview/download_preview.jsp?fileid=4759072&resid=292840&lid=19498&preview=preview
                " target="_blank">课程成绩评定标准
        </a>
    </TD>
    <td class="center common align_c"><a href="###" class="search"
        onClick="MM_goToURL('self','/meol/homepage/common/attribute_file.jsp?_style=new03&lid=19498&resid=292840')"></a>
    </td>
</TR>
<TR><TD><img src="/meol/common/icons/word.gif">&nbsp; <a href=" /meol/common/script/preview/download_preview.jsp?fileid=4819270&resid=302664&lid=19498&preview=preview " target="_blank">2025-2026-2学分置换证明 </a></TD></TR>
'''

print("=== 形态 A: 多文件列表 ===")
# 直接调 files_of 的解析部分需要网络,这里复制同一正则验证
import re, urllib.parse
out = []
for m in re.finditer(
        r'icons/([a-z0-9_]+)\.(?:gif|png)"[^>]*>\s*(?:&nbsp;)?\s*'
        r'<a[^>]*href="\s*([^"]*download_preview\.jsp[^"]*)"[^>]*>([^<]*)</a>',
        HTML_A, re.S):
    icon, href, name = m.group(1), m.group(2), m.group(3)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(re.sub(r"\s+", "", href)).query)
    out.append((icon, (q.get("fileid") or [""])[0], (q.get("resid") or [""])[0],
                re.sub(r"\s+", " ", name).strip()))

chk("条目数", len(out), 2)
chk("第1条", out[0], ("pdf", "4759072", "292840", "课程成绩评定标准"))
chk("第2条", out[1], ("word", "4819270", "302664", "2025-2026-2学分置换证明"))

# ---------- 形态 B: 单文件详情页 ----------
HTML_B = '''<div class="h1-title">
    <h1> 第1章 程序设计和C语言（含算法） </h1>
    <h2> 文件名:第1章 程序设计和C语言（含算法）.pdf <span style="font-size: 14px;padding: 0 10px 0 0;"> (3.0M ) </span>
    <a class="icon32 lv-download" href="/meol/common/script/download.jsp?fileid=2182951&resid=169658">下载</a> </h2>
</div>'''

print("\n=== 形态 B: 单文件详情页 ===")
# 走真实函数,只把网络层换掉
zl.get = lambda op, path, timeout=60: (
    "https://umooc.gdgm.cn/meol/buildless/resFolderViewList.do?folderid=169657", HTML_B.encode("gbk", "replace"))
got = zl.files_of(None, "folderid=169657&lid=19808&columnId=265113", "19808")
chk("条目数", len(got), 1)
if got:
    chk("resid", got[0]["resid"], "169658")
    chk("fileid", got[0]["fileid"], "2182951")
    chk("icon", got[0]["icon"], "pdf")
    chk("fullname", got[0]["fullname"], "第1章 程序设计和C语言（含算法）.pdf")
    chk("name(去扩展)", got[0]["name"], "第1章 程序设计和C语言（含算法）")

# ---------- 形态 A 走真实函数 ----------
print("\n=== 形态 A 走真实 files_of ===")
zl.get = lambda op, path, timeout=60: ("x", HTML_A.encode("utf-8"))
got = zl.files_of(None, "folderid=292660&lid=19498&columnId=353829", "19498")
chk("条目数", len(got), 2)
chk("resid[0]", got[0]["resid"] if got else None, "292840")

print("\n结果: %d 通过, %d 失败" % (ok, fail))
sys.exit(1 if fail else 0)