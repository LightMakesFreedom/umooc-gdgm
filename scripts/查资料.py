# -*- coding: utf-8 -*-
"""优慕课(广东工贸 THEOL)课程资料查看与下载。

用法:
    python 查资料.py <courseId>                     # 列出该课程所有栏目的资料(汇总)
    python 查资料.py <courseId> --tree              # 只看栏目结构(不拉文件)
    python 查资料.py <courseId> --column <columnId> # 只看某个栏目
    python 查资料.py <courseId> --download <下载目录> [--column <columnId>]
                                                    # 下载(默认全部栏目)
    python 查资料.py --courses                      # 先看有哪些课程 ID

判定"有资料"的栏目: 栏目页跳到 resFolderViewList.do 的才有文件列表,
其余(教学大纲/教师信息/答疑讨论等)是纯页面,不是文件。

下载走 /meol/common/script/download.jsp(唯一通用端点):
  Content-Disposition 带真实文件名(PDF/Word/txt/图片都适用)。
  ⚠️ 不要用 /meol/analytics/resPdfShow.do —— 它对 PDF 能出但 Word 返回 0 字节。
"""
import importlib.util, os, re, sys, time, urllib.parse, urllib.request

spec = importlib.util.spec_from_file_location(
    "chk", os.path.join(os.path.dirname(os.path.abspath(__file__)), "查作业.py"))
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

# 平台限速: 相邻请求间隔(秒)。太快会撞并发上限,排队反而更慢。
GAP = float(os.environ.get("UMOOC_GAP") or 1.0)

# 图标 -> 扩展名猜测(仅在没有 Content-Disposition 时兜底;实测平台几乎总会给真名)
ICON_EXT = {"pdf": ".pdf", "word": ".docx", "excel": ".xlsx", "ppt": ".pptx",
            "photo": ".png", "text": ".txt", "zip": ".zip", "rar": ".rar",
            "video": ".mp4", "audio": ".mp3"}

_last = [0.0]


def pace():
    d = time.time() - _last[0]
    if d < GAP:
        time.sleep(GAP - d)
    _last[0] = time.time()


def get(op, path, timeout=60):
    pace()
    return chk.fetch(op, chk.SITE + path, timeout=timeout)


# ---------------------------------------------------------------- 栏目树
def columns(op, cid):
    """课程页 -> [(columnId, 栏目名)]。含重复 id(同一栏目在不同分组下出现)。"""
    _, b = get(op, "/meol/jpk/course/layout/newpage/index.jsp?courseId=%s" % cid, timeout=45)
    t = chk.dec(b)
    out, seen = [], set()
    for m in re.finditer(
            r'course_column_preview_transfer\.jsp\?tagbug=client&columnId=(\d+)"[^>]*>\s*'
            r'<span[^>]*>([^<]+)</span>', t):
        col, name = m.group(1), m.group(2).strip()
        if (col, name) in seen:
            continue
        seen.add((col, name))
        out.append((col, name))
    return out


# ---------------------------------------------------------------- 资源列表
def folder_of(op, col):
    """栏目页 -> 跳转后的真实视图端点(相对路径+参数)。

    ⚠️ 栏目有两种跳转目标,都要认:
      1. resFolderViewList.do  —— 资源文件夹(上课文档/练习题/章节)
      2. courseResource.jsp    —— "课程资源"独立目录树(技术资料/教学资料)
    """
    fu, b = get(op, "/meol/jpk/course/course_column_preview_transfer.jsp"
                    "?tagbug=client&columnId=%s" % col, timeout=45)
    t = chk.dec(b)
    m = re.search(r'resFolderViewList\.do\?([^"\'\s>]+)', t)
    if m:
        return ("folder", m.group(1))
    if "courseResource.jsp" in fu or "courseResource.jsp" in t:
        q = urllib.parse.urlparse(fu.replace(chk.SITE, "")).query
        return ("resource", q)
    return None


def res_tree_of(op, query, cid):
    """'课程资源'目录树 -> 文件列表。

    结构: courseResource.jsp 里两个 iframe —— left.jsp(目录树) + listview.jsp(文件)。
    目录树由 JS 异步拉,静态 HTML 里拿不到,所以直接遍历 listview 的 folderid 目录:
    folderid=0 是根,子目录 id 从 listview 返回的链接里拿。
    """
    out, seen, queue = [], set(), [("0", "课程资源")]
    while queue:
        fid, label = queue.pop(0)
        if fid in seen:
            continue
        seen.add(fid)
        p = "/meol/common/script/listview.jsp?groupid=4&lid=%s&folderid=%s" % (cid, fid)
        try:
            _, b = get(op, p, timeout=60)
        except Exception:
            continue
        t = chk.dec(b)
        # 子目录: listview 里的 folderid=NNN 链接
        for m in re.finditer(r'folderid=(\d+)[^"\']*["\'][^>]*>([^<]{1,60})<', t):
            sub, nm = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
            if sub != fid and sub not in seen:
                queue.append((sub, nm or ("目录%s" % sub)))
        # 文件: 与该目录同形态的 download_preview 链接
        for m in re.finditer(
                r'href="\s*([^"]*download_preview\.jsp[^"]*)"[^>]*>([^<]{1,80})</a>', t, re.S):
            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(re.sub(r"\s+", "", m.group(1))).query)
            rid = (q.get("resid") or [""])[0]
            if not rid:
                continue
            out.append({"name": re.sub(r"\s+", " ", chk.html.unescape(m.group(2))).strip(),
                        "icon": "unknown", "fileid": (q.get("fileid") or [""])[0],
                        "resid": rid, "cid": cid, "group": label})
    return out


def files_of(op, query, cid):
    """资源列表页 -> [{name, icon, fileid, resid}]"""
    _, b = get(op, "/meol/buildless/resFolderViewList.do?" + query, timeout=60)
    t = chk.dec(b)
    out = []

    # 形态 A: 多文件列表 —— 图标 + download_preview.jsp 链接(上课文档/练习题等)
    for m in re.finditer(
            r'icons/([a-z0-9_]+)\.(?:gif|png)"[^>]*>\s*(?:&nbsp;)?\s*'
            r'<a[^>]*href="\s*([^"]*download_preview\.jsp[^"]*)"[^>]*>([^<]*)</a>',
            t, re.S):
        icon, href, name = m.group(1), m.group(2), m.group(3)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(re.sub(r"\s+", "", href)).query)
        fid, rid = (q.get("fileid") or [""])[0], (q.get("resid") or [""])[0]
        if not rid:
            continue
        out.append({"name": re.sub(r"\s+", " ", chk.html.unescape(name)).strip(),
                    "icon": icon, "fileid": fid, "resid": rid, "cid": cid})

    # 形态 B: 单文件详情页 —— 直接给"文件名:XXX.pdf" + 一个 download.jsp 链接
    # (章节栏目里一栏目挂一个资源时是这种页面,没有图标列表)
    if not out:
        mname = re.search(r'文件名[:：]\s*([^<]+?)\s*<', t)
        mdown = re.search(r'href="([^"]*download\.jsp\?[^"]*)"', t)
        if mname and mdown:
            fn = chk.html.unescape(mname.group(1)).strip()
            q = urllib.parse.parse_qs(urllib.parse.urlparse(mdown.group(1)).query)
            rid = (q.get("resid") or [""])[0]
            fid = (q.get("fileid") or [""])[0]
            ext = os.path.splitext(fn)[1].lower().lstrip(".")
            icon = {"pdf": "pdf", "doc": "word", "docx": "word", "xls": "excel",
                    "xlsx": "excel", "ppt": "ppt", "pptx": "ppt", "zip": "zip",
                    "rar": "rar", "txt": "text", "png": "photo", "jpg": "photo",
                    "jpeg": "photo", "mp4": "video"}.get(ext, "unknown")
            if rid:
                out.append({"name": os.path.splitext(fn)[0], "icon": icon,
                            "fileid": fid, "resid": rid, "cid": cid,
                            "fullname": fn})
    return out


def scan(op, cid, only_col=None, tree_only=False):
    """遍历栏目 -> {栏目名: [文件]}。only_col 指定则只查该栏目。

    ⚠️ 栏目树里同一个 columnId 会出现多次(不同分组下的别名),例如 323001 同时
    叫"课程练习题"和"理论练习题"。**必须先按 columnId 去重再抓**,否则同一批
    文件会被拉好几遍。文件层面再按 resid 去一次重,防同一文件挂多个栏目。

    ⚠️ 反向的坑:**不同 columnId 可能同名**。19498 有两个"课堂练习题"
    (340728 装 txt/zip,328179 装 docx)。所以字典的 key 必须带 columnId,
    只用栏目名会互相覆盖、静默丢文件(踩过一次)。
    """
    cols = columns(op, cid)
    if only_col:
        cols = [c for c in cols if c[0] == str(only_col)] or [("?", "未知栏目")]
    if tree_only:
        return cols, {}

    res = {}
    seen_res = set()
    done_col = set()          # 已抓过的 columnId,别名直接跳过
    for col, name in cols:
        if col in done_col:
            continue
        done_col.add(col)
        try:
            kind_q = folder_of(op, col)
        except Exception as e:
            print("  [跳过] %-22s 栏目页失败: %s" % (name[:20], e), file=sys.stderr)
            continue
        if not kind_q:
            continue
        kind, q = kind_q
        try:
            if kind == "resource":
                fl = res_tree_of(op, q, cid)
            else:
                fl = files_of(op, q, cid)
        except Exception as e:
            print("  [跳过] %-22s 文件列表失败: %s" % (name[:20], e), file=sys.stderr)
            continue
        uniq = []
        for f in fl:
            if f["resid"] in seen_res:
                continue
            seen_res.add(f["resid"])
            f["columnId"] = col
            uniq.append(f)
        if uniq:
            # key 带 columnId: 同名不同栏目不会互相覆盖
            res["%s#%s" % (name, col)] = uniq
    return cols, res


# ---------------------------------------------------------------- 展示
def show(cid, cols, res, tree_only=False):
    print("\n课程 %s | 栏目 %d 个" % (cid, len(cols)))
    if tree_only:
        for col, name in cols:
            print("  %-8s %s" % (col, name))
        print()
        return
    if not res:
        print("(没有找到任何可下载的资料)")
        print()
        return
    total = sum(len(v) for v in res.values())
    print("有资料的栏目 %d 个,文件共 %d 个\n" % (len(res), total))
    for key, fl in res.items():
        # key 形如 "栏目名#columnId";同名栏目只在冲突时才显示 columnId
        name, _, colid = key.partition("#")
        same = sum(1 for k in res if k.partition("#")[0] == name) > 1
        print("── %s (%d)%s" % (name, len(fl), ("  [columnId %s]" % colid) if same else ""))
        last_group = None
        for f in fl:
            g = f.get("group")
            if g and g != last_group:
                print("   [%s]" % g)
                last_group = g
            ext = ICON_EXT.get(f["icon"], "") if f["icon"] != "unknown" else ""
            label = (f.get("fullname") or (f["name"] + ext))[:50]
            print("   %-52s %-6s resid=%s" % (label, f["icon"], f["resid"]))
    print("\n下载: python 查资料.py %s --download <目录> [--column <columnId>]" % cid)
    print()


# ---------------------------------------------------------------- 下载
def safe(name):
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip()[:120] or "未命名"


def download(op, res, outdir, cid, retries=3, skip_exist=True):
    """下载。断点续传式:已存在的同名文件默认跳过,失败自动重试。

    ⚠️ 大批量下载时平台会中途掐连接(Remote end closed connection),
    85/221 这种失败率很常见。重试 + 跳过已下载是必要的,别一次失败就整批放弃。
    """
    os.makedirs(outdir, exist_ok=True)
    ok = fail = skip = 0
    for key, fl in res.items():
        name, _, colid = key.partition("#")
        same = sum(1 for k in res if k.partition("#")[0] == name) > 1
        dirname = ("%s_%s" % (name, colid)) if same else name
        for f in fl:
            # 有 group(课程资源目录树)时多一层子目录,否则按栏目名分
            sub = os.path.join(outdir, safe(dirname))
            if f.get("group"):
                sub = os.path.join(sub, safe(f["group"]))
            os.makedirs(sub, exist_ok=True)

            # 目标文件名(尽量提前定好,方便跳过已存在的)
            guess = safe(f.get("fullname") or (f["name"] + ICON_EXT.get(f["icon"], "")))
            if skip_exist:
                stem = os.path.splitext(guess)[0]
                # 已存在判定: 同名,或"文件名(1).ext"这种撞名副本,或去掉扩展名前缀相同
                # (列表标题 vs 服务端真名可能不同,如 信创知识大赛群 / ...群二维码)
                hit = None
                for x in os.listdir(sub):
                    xs = os.path.splitext(x)[0]
                    xs_norm = re.sub(r"\(\d+\)$", "", xs)
                    if xs_norm == stem or (stem and xs_norm.startswith(stem)) \
                            or (xs_norm and stem.startswith(xs_norm)):
                        hit = x
                        break
                if hit:
                    print("  [跳过] %s (已存在)" % hit[:60])
                    skip += 1
                    continue

            body = cd = None
            err = ""
            for attempt in range(retries):
                pace()
                p = ("/meol/common/script/download.jsp?fileid=%s&resid=%s&lid=%s&preview=preview"
                     % (f["fileid"], f["resid"], cid))
                try:
                    req = urllib.request.Request(
                        chk.SITE + p,
                        headers={"User-Agent": chk.UA,
                                 "Referer": chk.SITE + "/meol/common/homework.html"})
                    with op.open(req, timeout=180) as r:
                        body = r.read()
                        cd = r.headers.get("Content-Disposition") or ""
                    # 空响应 / 错误页 当失败,可重试
                    # ⚠️ 错误页前面有几十个换行,必须先 strip 再判断,
                    #    否则 body[:15].lstrip() 是空串、startswith 永远 False,
                    #    777 字节的 error.css 页面就被当成"下载成功"了。
                    head = (body or b"")[:400].lstrip().lower()
                    if not body or head.startswith(b"<!doctype") or head.startswith(b"<html"):
                        err = "返回空或错误页(%d 字节)" % len(body or b"")
                        body = None
                    else:
                        err = ""
                        break
                except Exception as e:
                    err = str(e) or repr(e)
                    body = None
                # 重试前退避,平台掐连接后立刻再打只会继续失败
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))

            if body is None:
                # PDF 走 download.jsp 有时只回 777 字节错误页,换 resPdfShow.do 再试一次。
                # (反过来不行: resPdfShow 对 Word 返回 0 字节,所以只给 PDF 用)
                if f["icon"] == "pdf":
                    try:
                        pace()
                        p2 = "/meol/analytics/resPdfShow.do?resId=%s&lid=%s" % (f["resid"], cid)
                        req = urllib.request.Request(
                            chk.SITE + p2,
                            headers={"User-Agent": chk.UA,
                                     "Referer": chk.SITE + "/meol/common/homework.html"})
                        with op.open(req, timeout=180) as r:
                            b2 = r.read()
                        if b2[:4] == b"%PDF":
                            body, cd = b2, ""
                            print("  [回退] resPdfShow 取到 %d 字节" % len(b2))
                    except Exception:
                        pass
            if body is None:
                print("  [失败] %s :: %s" % (guess[:50], err[:60]))
                fail += 1
                continue

            # 文件名优先用 Content-Disposition,其次页面给的完整文件名,最后标题+图标后缀
            m = re.search(r'filename="?([^";]+)"?', cd or "")
            if m:
                fn = urllib.parse.unquote(m.group(1))
            elif f.get("fullname"):
                fn = f["fullname"]
            else:
                fn = f["name"] + ICON_EXT.get(f["icon"], "")
            fn = safe(fn)
            # 撞名加序号
            full = os.path.join(sub, fn)
            if os.path.exists(full):
                stem, ext = os.path.splitext(fn)
                i = 1
                while os.path.exists(os.path.join(sub, "%s(%d)%s" % (stem, i, ext))):
                    i += 1
                full = os.path.join(sub, "%s(%d)%s" % (stem, i, ext))
            open(full, "wb").write(body)
            print("  [OK %7d] %s" % (len(body), os.path.relpath(full, outdir)[:70]))
            ok += 1
    print("\n完成: 成功 %d,跳过 %d(已存在),失败 %d -> %s" % (ok, skip, fail, outdir))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--help" in args:
        print(__doc__)
        sys.exit()
    if "--courses" in args:
        # 复用查作业的课表
        for cid, name in sorted(chk.COURSES.items(), key=lambda x: x[1]):
            print("  %-8d %s" % (cid, name))
        sys.exit()

    cid = args[0]
    only = None
    if "--column" in args:
        i = args.index("--column")
        only = args[i + 1]
    outdir = None
    if "--download" in args:
        i = args.index("--download")
        outdir = args[i + 1] if i + 1 < len(args) else "."

    op = chk.session()
    cols, res = scan(op, cid, only, tree_only="--tree" in args)
    if outdir:
        if not res:
            print("(没有可下载的资料)")
        else:
            download(op, res, outdir, cid)
    else:
        show(cid, cols, res, tree_only="--tree" in args)