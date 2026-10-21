# -*- coding: utf-8 -*-
"""优慕课(广东工贸 THEOL)作业查询。

用法:
    python 查作业.py                      # 当前学期真·未交(默认)
    python 查作业.py --history            # 连上学期及更早的存量一起列
    python 查作业.py --all                # 全部作业(含已交,带分数)
    python 查作业.py <courseId> <hwtId>   # 读该次作业的要求与我的草稿
    python 查作业.py --courses            # 重抓课程列表(加新课时用)

凭据: 同目录 config.json(username/password/um),或环境变量 UMOOC_USER/UMOOC_PASS。
会话: 同目录 session.json(cookie),过期才登录——**平台有并发登录上限,别反复登**。

判定"已交"的硬标准: 有分数 mark 或 有 finishTime。
  ⚠️ submitStruts 是"提交窗口还开着",不是"已提交"! 拿它判断会报一堆乌龙。
"""
import sys, os, json, re, html, urllib.parse, urllib.request, http.cookiejar, ssl, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://umooc.gdgm.cn"
# config.json 放技能根目录或 scripts/ 都认;session.json 是运行时状态,挨着脚本放
CFG = os.path.join(BASE, "config.json")
if not os.path.exists(CFG):
    CFG = os.path.join(BASE, "..", "config.json")
COOKIEF = os.path.join(BASE, "session.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0")
SEM_START = "2026-09-01"      # 本学期(2026-2027-1)起点,之前算历史存量

# ponytail: courseId 写死。平台只给"有作业的课"的列表,新增课程手动加一行,
# 或跑 --courses 重新抓。漏一门课就可能漏一堆作业,所以默认会跟首页组件交叉校验。
# ↓ 占位示例:首次使用先跑 `python 查作业.py --courses`,把生成的 COURSES 行贴回来
COURSES = {
    11111: "示例课程A(换成你的)",
    22222: "示例课程B(换成你的)",
}


# ---------------------------------------------------------------- 会话
def load_cfg():
    cfg = {}
    if os.path.exists(CFG):
        try:
            cfg = json.load(open(CFG, encoding="utf-8"))
        except Exception as e:
            print("[!] config.json 读不了: %s" % e)
    user = os.environ.get("UMOOC_USER") or cfg.get("username") or ""
    pwd = os.environ.get("UMOOC_PASS") or cfg.get("password") or ""
    return user.strip(), pwd.strip(), str(cfg.get("um") or "").strip()


def new_opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    cj = http.cookiejar.CookieJar()
    if os.path.exists(COOKIEF):
        try:
            for c in json.load(open(COOKIEF, encoding="utf-8")):
                cj.set_cookie(http.cookiejar.Cookie(
                    0, c["name"], c["value"], None, False,
                    c.get("domain", ""), True, c.get("domain", "").startswith("."),
                    c.get("path", "/"), True, bool(c.get("secure")),
                    c.get("expires"), False, None, None, {}, False))
        except Exception:
            pass
    # ProxyHandler({}) 必须的:系统代理会缓存页面,拿到过期 token
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ctx)), cj


def save_cookies(cj):
    items = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
              "secure": bool(c.secure), "expires": c.expires} for c in cj]
    json.dump(items, open(COOKIEF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def fetch(op, url, referer=None, timeout=30, data=None):
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Connection": "close"}
    if referer:
        h["Referer"] = referer
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h)
    with op.open(req, timeout=timeout) as r:
        return r.geturl(), r.read()


def dec(b):
    for e in ("utf-8", "gb18030"):
        try:
            return b.decode(e)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def session_alive(op):
    """已登录的 personal.do 是大页面;未登录返回 782 字节的'您尚未登录系统'"""
    try:
        _, b = fetch(op, SITE + "/meol/personal.do", timeout=25)
        return len(b) > 3000 and "尚未登录" not in dec(b)
    except Exception:
        return False


def login(op, cj):
    user, pwd, _ = load_cfg()
    if not user or not pwd:
        sys.exit("缺账号密码:填 config.json 或设 UMOOC_USER/UMOOC_PASS")
    _, page = fetch(op, SITE + "/meol/index.do", timeout=30)
    m = re.search(r'name=["\']logintoken["\']\s+value=["\']([^"\']*)', dec(page))
    token = m.group(1) if m else str(int(datetime.datetime.now().timestamp() * 1000))
    final, _ = fetch(op, SITE + "/meol/loginCheck.do", referer=SITE + "/meol/index.do",
                     data={"logintoken": token, "IPT_LOGINUSERNAME": user,
                           "IPT_LOGINPASSWORD": pwd})
    if "personal.do" not in final:
        # 平台对并发登录的报错就藏在登录页里,不细解析,直接给出最终 URL 让人看
        sys.exit("登录失败(可能撞并发上限,稍后再试): %s" % final[:120])
    save_cookies(cj)


def session():
    op, cj = new_opener()
    if not session_alive(op):
        login(op, cj)
        print("(会话已过期,已重新登录)")
    return op


# ---------------------------------------------------------------- 解析
def text_of(raw):
    """平台 content/hwaAnswer 是双层编码:正文藏在 hidden input 的 value 里,
    还要再 html.unescape 一次。页面里还插了混淆 JS 防爬,直接取 body 会拿到垃圾。"""
    if not raw:
        return ""
    m = re.search(r"id='\d+_content'.*?value='(.*?)'\s*>", raw, re.S)
    s = html.unescape(m.group(1)) if m else raw
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?is)<img[^>]*>", "[图片]", s)
    s = re.sub(r"<[^>]+>", "\n", s)
    s = html.unescape(s).replace("\xa0", " ")
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


def api(op, path, **params):
    u = SITE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    _, b = fetch(op, u, SITE + "/meol/common/homework.html", timeout=25)
    try:
        return json.loads(dec(b))
    except Exception:
        return {}


def collect(op):
    """拉全部作业。没分数的再补一次请求拿 finishTime——已批分的不用查。"""
    _, _, um = load_cfg()
    out = []
    for cid, name in COURSES.items():
        d = api(op, "/meol/hw/stu/hwStuHwtList.do", courseId=cid,
                hwType="blended_info", page=1, rows=50)
        for h in d.get("datas", {}).get("hwtList", []):
            mark = h.get("mark")
            ft = None
            if not mark:
                d2 = api(op, "/meol/hw/stu/hwTaskAnswerView.do",
                         courseId=cid, um=um, hwtId=h.get("id"))
                ft = d2.get("datas", {}).get("finishTime")
            out.append({"cid": cid, "course": name, "title": h.get("title"),
                        "id": h.get("id"), "deadline": str(h.get("deadLine"))[:10],
                        "mark": mark, "done": bool(mark or ft)})
    return out


def widget_pending(op):
    """平台首页互动提醒:'N 门课程有待提交作业'+课程名。用来交叉校验有没有漏课。"""
    _, b = fetch(op, SITE + "/meol/welcomepage/student/interaction_reminder_v8.jsp",
                 SITE + "/meol/personal.do", timeout=30)
    t = text_of(dec(b))
    m = re.search(r"(\d+)\s*门课程有待提交作业\s*([\u4e00-\u9fa5A-Za-z0-9()（）\-]*)", t)
    return (int(m.group(1)), m.group(2).strip()) if m else (None, "")


def show(op, mode):
    rows = collect(op)
    today = datetime.date.today().isoformat()
    todo = [r for r in rows if not r["done"]]
    done = [r for r in rows if r["done"]]
    pend_courses = {r["course"] for r in todo}

    try:
        wn, wname = widget_pending(op)
        if wn is not None and wn > len(pend_courses):
            print("\n[!] 校验警告:平台首页说有 %d 门待提交作业(%s),本工具只覆盖 %d 门(%s)。"
                  "可能漏课,跑 --courses 重抓,或手动往 COURSES 加。"
                  % (wn, wname or "?", len(pend_courses),
                     "/".join(sorted(pend_courses)) or "无"))
    except Exception:
        pass

    cur = sorted((r for r in todo if r["deadline"] >= SEM_START),
                 key=lambda r: r["deadline"], reverse=True)
    his = sorted((r for r in todo if r["deadline"] < SEM_START),
                 key=lambda r: r["deadline"], reverse=True)

    print("\n===== 未交·当前学期 (%d) =====" % len(cur))
    for r in cur:
        if r["deadline"] >= today:
            left = (datetime.date.fromisoformat(r["deadline"])
                    - datetime.date.fromisoformat(today)).days
            tag = "★还能交,剩%d天" % left
        else:
            tag = "已逾期%d天" % (datetime.date.fromisoformat(today)
                              - datetime.date.fromisoformat(r["deadline"])).days
        print("%s  %-18s %-14s %s\n            读要求: 查作业.py %d %d"
              % (r["deadline"], tag, r["course"], r["title"], r["cid"], r["id"]))

    if mode in ("--history", "--all"):
        print("\n===== 未交·历史存量(上学期及更早, %d) =====" % len(his))
        for r in his:
            print("%s  %-14s %s   [查作业.py %d %d]"
                  % (r["deadline"], r["course"], r["title"], r["cid"], r["id"]))
    elif his:
        print("\n(另有 %d 个历史存量从没交过;加 --history 看)" % len(his))

    if mode == "--all":
        print("\n===== 已交 (%d) =====" % len(done))
        for r in sorted(done, key=lambda r: r["deadline"], reverse=True):
            print("%s  %-14s %-34s %s" % (r["deadline"], r["course"],
                                          str(r["title"])[:34], r["mark"] or "已交"))
    print()


def read_mode(op, cid, hwt):
    _, _, um = load_cfg()
    d = api(op, "/meol/hw/stu/hwTaskAnswerView.do", courseId=cid, um=um, hwtId=hwt)
    ds = d.get("datas", {})
    if not ds:
        sys.exit("读不到(作业ID或课程ID不对?)")
    print("\n=== %s ===" % ds.get("title"))
    print("课程   : %s" % COURSES.get(int(cid), cid))
    print("时间   : %s ~ %s   满分 %s" % (str(ds.get("startDateTime"))[:10],
                                        str(ds.get("deadLine"))[:10], ds.get("fullMark")))
    print("\n---------- 作业要求 ----------")
    print(text_of(ds.get("content")) or "(无)")
    print("\n---------- 我的草稿 ----------")
    print(text_of(ds.get("hwaAnswer")) or "(空)")
    print()


def courses_mode(op):
    """重抓课程列表。注意:平台只给'有作业的课',不是全部在读课程。"""
    _, b = fetch(op, SITE + "/meol/welcomepage/student/course_list_v8.jsp",
                 SITE + "/meol/personal.do", timeout=45)
    found = {}
    for m in re.finditer(r'courseId=(\d+)\'[^>]*title="([^"]+)"', dec(b)):
        found[int(m.group(1))] = m.group(2).strip()
    print("\n平台返回 %d 门课(只有挂作业的):" % len(found))
    for cid, name in sorted(found.items(), key=lambda x: x[1]):
        tag = "" if cid in COURSES else "   <<< 本地 COURSES 里没有,要加"
        print("  %-8d %s%s" % (cid, name, tag))
    print("\n# 复制下面这行替换脚本里的 COURSES:")
    print("COURSES = {" + ", ".join("%d: %r" % (k, v) for k, v in sorted(found.items())) + "}")
    print()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        read_mode(session(), sys.argv[1], sys.argv[2])
    elif "--courses" in sys.argv:
        courses_mode(session())
    else:
        show(session(), sys.argv[1] if len(sys.argv) > 1 else "")
