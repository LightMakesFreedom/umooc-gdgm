# -*- coding: utf-8 -*-
"""优慕课作业提交(图片走 SerUpload 嵌入富文本 answer)。

用法:
    python 提交作业.py <courseId> <hwtId> <标题> <图片1> [图片2 ...]
        上传图片 -> 构造 answer HTML -> POST hwStuSubmitDo.do
    python 提交作业.py <courseId> <hwtId> <标题> [图片...] --zip <包.zip>
        图片 + zip 附件一起交(zip 走 SerUpload?action=uploadfile)
    python 提交作业.py --verify <courseId> <hwtId>
        读回已提交内容: 反转义数 img、逐个 GET 验证图片可访问

图片相对路径基于本脚本所在目录的上一级(技能根目录)或 cwd,绝对路径也行。
⚠️ 提交是不可逆的外部动作,用前必须得到用户明确同意。
⚠️ 逾期作业平台硬关闭,对逾期 hwtId 提交会返回"作业未开始/已结束"。

实测记录(2026-10-20/21, 多份作业全流程提交并回读验证通过):
  上传 /meol/servlet/SerUpload?action=uploadimage (multipart, 字段 action+upfile)
  返回 {"state":"SUCCESS","url":"/meol/common/ckeditor/openfile.jsp?id=..."}
  附件上传 /meol/servlet/SerUpload?action=uploadfile (同名字段 upfile, .zip/.rar/.tar 等允许)
  提交 /meol/hw/stu/hwStuSubmitDo.do (multipart, 字段 courseId/um/hwtId/answer)
  返回 {"message":"提交成功","status":1}; hwTaskAnswerView.do 可见 finishTime
"""
import importlib.util, json, os, re, sys, urllib.request

spec = importlib.util.spec_from_file_location(
    "chk", os.path.join(os.path.dirname(os.path.abspath(__file__)), "查作业.py"))
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve(path):
    if os.path.isabs(path) and os.path.exists(path):
        return path
    for base in (os.getcwd(), SKILL_ROOT):
        p = os.path.join(base, path)
        if os.path.exists(p):
            return p
    sys.exit("找不到图片: %s" % path)


def upload(op, file_path, action="uploadimage", ctype="image/png"):
    """上传文件到 SerUpload。图片 action=uploadimage;zip 等附件 action=uploadfile。"""
    data = open(file_path, "rb").read()
    name = os.path.basename(file_path)
    B = "----umboundary9876543210"
    body = ("--%s\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\n%s\r\n"
            % (B, action)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"upfile\"; filename=\"%s\"\r\n"
             "Content-Type: %s\r\n\r\n" % (B, name, ctype)).encode() + data + b"\r\n"
    body += ("--%s--\r\n" % B).encode()
    h = {"User-Agent": chk.UA, "Content-Type": "multipart/form-data; boundary=%s" % B,
         "Referer": chk.SITE + "/meol/common/homework.html"}
    req = urllib.request.Request(chk.SITE + "/meol/servlet/SerUpload?action=" + action,
                                 data=body, headers=h)
    with op.open(req, timeout=120) as r:
        d = json.loads(chk.dec(r.read()))
    if d.get("state") != "SUCCESS":
        raise RuntimeError("上传失败: %s" % d)
    return d["url"]


def post_multipart(op, url, fields):
    B = "----wbboundary5566778899"
    body = b""
    for k, v in fields:
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (B, k, v)).encode("utf-8")
    body += ("--%s--\r\n" % B).encode()
    h = {"User-Agent": chk.UA, "Content-Type": "multipart/form-data; boundary=%s" % B,
         "Referer": chk.SITE + "/meol/common/homework.html"}
    req = urllib.request.Request(url, data=body, headers=h)
    with op.open(req, timeout=120) as r:
        return chk.dec(r.read())


def build_answer(title, urls, files, zip_url=None, zip_name=""):
    p = ["<p>%s（实测，共%d张图）：</p>" % (title, len(urls))]
    for i, (u, fn) in enumerate(zip(urls, files), 1):
        p.append("<p><strong>%d. %s</strong></p>" % (i, os.path.splitext(fn)[0]))
        p.append("<p><img src=\"%s%s\" /></p>" % (chk.SITE, u))
    if zip_url:
        p.append("<p><strong>附件：%s</strong>（点击下载）：</p>" % zip_name)
        p.append("<p><a href=\"%s%s\">%s</a></p>" % (chk.SITE, zip_url, zip_name))
    return "".join(p)


def do_submit(op, course_id, hwt_id, title, files, zip_path=None):
    _, _, um = chk.load_cfg()
    urls = []
    for f in files:
        u = upload(op, resolve(f))
        urls.append(u)
        print("  上传 %-28s -> %s" % (os.path.basename(f), u[:72]))
    zip_url = None
    zip_name = ""
    if zip_path:
        zip_url = upload(op, resolve(zip_path), "uploadfile", "application/zip")
        zip_name = os.path.basename(zip_path)
        print("  上传 %-28s -> %s" % (zip_name, zip_url[:72]))
    answer = build_answer(title, urls, [os.path.basename(f) for f in files],
                          zip_url, zip_name)
    resp = post_multipart(op, chk.SITE + "/meol/hw/stu/hwStuSubmitDo.do",
                          [("courseId", str(course_id)), ("um", um),
                           ("hwtId", str(hwt_id)), ("answer", answer)])
    print("  hwStuSubmitDo 响应: %s" % resp[:300])
    d = chk.api(op, "/meol/hw/stu/hwTaskAnswerView.do",
                courseId=course_id, um=um, hwtId=hwt_id)
    print("  finishTime: %s" % d.get("datas", {}).get("finishTime"))


def do_verify(op, course_id, hwt_id):
    _, _, um = chk.load_cfg()
    d = chk.api(op, "/meol/hw/stu/hwTaskAnswerView.do",
                courseId=course_id, um=um, hwtId=hwt_id)
    ds = d.get("datas", {})
    # 平台对 content/hwaAnswer 是双层 HTML 转义,含 <>& 的行要 unescape 两次才见原文
    ans = __import__("html").unescape(
        __import__("html").unescape(ds.get("hwaAnswer") or ""))
    print("finishTime: %s" % ds.get("finishTime"))
    imgs = re.findall(r'<img[^>]*src="([^"]+)"', ans)
    zips = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', ans)
    print("img 数量: %d, 附件链接: %s"
          % (len(imgs), [n for _, n in zips] or "无"))
    ok = 0
    for u in imgs:
        req = urllib.request.Request(u, headers={"User-Agent": chk.UA})
        try:
            with op.open(req, timeout=30) as r:
                body = r.read()
                good = r.status == 200 and "image" in (r.headers.get("Content-Type") or "")
                ok += good
                print("  [%s %d字节] ...%s" % ("OK" if good else "BAD", len(body), u[-30:]))
        except Exception as e:
            print("  [ERR %s] ...%s" % (e, u[-30:]))
    print("共 %d/%d 张图片可访问" % (ok, len(imgs)))


if __name__ == "__main__":
    op = chk.session()
    args = sys.argv[1:]
    zip_path = None
    if "--zip" in args:
        i = args.index("--zip")
        zip_path = args[i + 1]
        del args[i:i + 2]
    if len(args) >= 3 and args[0] == "--verify":
        do_verify(op, args[1], args[2])
    elif len(args) >= 4:
        do_submit(op, args[0], args[1], args[2], args[3:], zip_path)
    else:
        print(__doc__)
