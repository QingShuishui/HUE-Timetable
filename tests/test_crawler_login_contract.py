from datetime import date, timedelta
from unittest.mock import patch

import importlib
import builtins

import utils.crawler as crawler


@patch(
    "utils.crawler.parse_table",
    return_value=[
        {
            "name": "软件测试技术",
            "code": "SIT",
            "teacher": "张三",
            "location": "S4409",
            "weeks": "1-16(周)",
            "time": "08:00-09:40",
            "day": "周一",
            "row": 0,
            "col": 0,
        }
    ],
)
@patch("utils.crawler.ddddocr.DdddOcr")
@patch("utils.crawler.requests.Session")
def test_login_and_get_schedule_uses_supplied_credentials(
    session_cls, ocr_cls, _parse_table
):
    session = session_cls.return_value
    ocr_cls.return_value.classification.return_value = "1234"

    response_home = type(
        "R", (), {"text": "", "status_code": 200, "url": "https://jwxt.hue.edu.cn"}
    )()
    response_sess = type(
        "R", (), {"text": "abc#111", "status_code": 200, "url": "https://jwxt.hue.edu.cn"}
    )()
    response_captcha = type(
        "R",
        (),
        {"content": b"img", "status_code": 200, "url": "https://jwxt.hue.edu.cn"},
    )()
    response_login = type(
        "R",
        (),
        {
            "text": "",
            "status_code": 200,
            "url": "https://jwxt.hue.edu.cn/xsMain.jsp",
        },
    )()
    response_table = type(
        "R",
        (),
        {
            "text": "<div id='timetableDiv'>2026春</div><table id='kbtable'></table>",
            "status_code": 200,
            "url": "https://jwxt.hue.edu.cn",
        },
    )()
    session.get.side_effect = [response_home, response_sess, response_captcha, response_table]
    session.post.side_effect = [response_login]

    username = "2026000000"
    password = "pw123"
    crawler.login_and_get_schedule(username, password)

    login_call = session.post.call_args_list[0]
    post_data = login_call.kwargs["data"]
    assert "2026000000" not in post_data["encoded"]
    schedule_call = session.get.call_args_list[3]
    assert schedule_call.args[0] == "https://jwxt.hue.edu.cn/jsxsd/xskb/xskb_list.do"

    scode, sxh = response_sess.text.split("#")
    expected = _expected_encoded(username, password, scode, sxh)
    assert post_data["encoded"] == expected

    # Prove the function doesn't ignore the supplied credentials: a second
    # call with different credentials must produce a different encoded payload.
    session_2 = session_cls.return_value.__class__()
    session_cls.side_effect = [session_2]
    session_2.get.side_effect = [response_home, response_sess, response_captcha, response_table]
    session_2.post.side_effect = [response_login]

    username_2 = "0000000000"
    password_2 = "pw999"
    crawler.login_and_get_schedule(username_2, password_2)
    post_data_2 = session_2.post.call_args_list[0].kwargs["data"]
    expected_2 = _expected_encoded(username_2, password_2, scode, sxh)
    assert post_data_2["encoded"] == expected_2
    assert post_data_2["encoded"] != post_data["encoded"]


@patch("utils.crawler.ddddocr.DdddOcr")
@patch("utils.crawler.requests.Session")
def test_login_and_get_schedule_falls_back_to_daily_schedule_when_main_schedule_empty(
    session_cls, ocr_cls
):
    session = session_cls.return_value
    ocr_cls.return_value.classification.return_value = "1234"

    response_home = type(
        "R", (), {"text": "", "status_code": 200, "url": "https://jwxt.hue.edu.cn"}
    )()
    response_sess = type(
        "R", (), {"text": "abc#111", "status_code": 200, "url": "https://jwxt.hue.edu.cn"}
    )()
    response_captcha = type(
        "R",
        (),
        {"content": b"img", "status_code": 200, "url": "https://jwxt.hue.edu.cn"},
    )()
    response_login = type(
        "R",
        (),
        {
            "text": "",
            "status_code": 200,
            "url": "https://jwxt.hue.edu.cn/xsMain.jsp",
        },
    )()
    response_empty_main = type(
        "R",
        (),
        {
            "text": "<div id='timetableDiv'>2026春</div><table id='kbtable'><tr></tr></table>",
            "status_code": 200,
            "url": "https://jwxt.hue.edu.cn/jsxsd/xskb/xskb_list.do",
        },
    )()

    fallback_dates = []

    def get_response(url, **_kwargs):
        if url == "https://jwxt.hue.edu.cn":
            return response_home
        if url.endswith("/Logon.do?method=logon&flag=sess"):
            return response_sess
        if url.endswith("/verifycode.servlet"):
            return response_captcha
        if url.endswith("/jsxsd/xskb/xskb_list.do"):
            return response_empty_main
        raise AssertionError(f"unexpected GET {url}")

    def post_response(url, data=None, **_kwargs):
        if url.endswith("/Logon.do?method=logon"):
            return response_login
        if url.endswith("/jsxsd/framework/main_index_loadkb.jsp"):
            rq = data["rq"]
            fallback_dates.append(rq)
            if rq in {"2026-03-02", "2026-03-09"}:
                week = 1 if rq == "2026-03-02" else 2
                return _response(_fallback_week_table_html(week))
            return _response(_empty_fallback_week_table_html())
        raise AssertionError(f"unexpected POST {url}")

    session.get.side_effect = get_response
    session.post.side_effect = post_response

    data, error = crawler.login_and_get_schedule("2026000000", "pw123")

    assert error is None
    assert data["semester_info"] == "2026春"
    assert data["courses"] == [
        {
            "name": "面向对象程序设计",
            "code": "SIT",
            "teacher": "",
            "location": "S4408计算机专业实验室",
            "weeks": "1-2(周)",
            "time": "08:00-09:40",
            "day": "周二",
            "row": 0,
            "col": 1,
        }
    ]

    semester_start = date(2026, 3, 2)
    expected_dates = {
        (semester_start + timedelta(days=(week - 1) * 7)).strftime("%Y-%m-%d")
        for week in range(1, 21)
    }
    assert set(fallback_dates) == expected_dates


def _response(text, status_code=200):
    return type(
        "R",
        (),
        {
            "text": text,
            "status_code": status_code,
            "url": "https://jwxt.hue.edu.cn",
        },
    )()


def _fallback_week_table_html(week):
    empty_row = "<tr><td>上午1-2节<br/>(01,02小节)<br/>08:00-09:40</td>" + "".join(
        "<td></td>" for _ in range(7)
    ) + "</tr>"
    first_row = (
        "<tr>"
        "<td>上午1-2节<br/>(01,02小节)<br/>08:00-09:40</td>"
        "<td></td>"
        "<td><p title='课程学分：1.5&lt;br/&gt;课程属性：必修&lt;br/&gt;"
        "课程名称：面向对象程序设计 SIT&lt;br/&gt;"
        f"上课时间：第{week}周 星期二 [01-02]节&lt;br/&gt;"
        "上课地点：S4408计算机专业实验室'>面向对象程序..S4408计算机专业实验室</p></td>"
        + "".join("<td></td>" for _ in range(5))
        + "</tr>"
    )
    header = (
        "<tr><td>周/节次</td><td>星期一</td><td>星期二</td><td>星期三</td>"
        "<td>星期四</td><td>星期五</td><td>星期六</td><td>星期日</td></tr>"
    )
    return "<table id='tab1' class='kb_table'>" + header + first_row + empty_row * 5 + "</table>"


def _empty_fallback_week_table_html():
    header = (
        "<tr><td>周/节次</td><td>星期一</td><td>星期二</td><td>星期三</td>"
        "<td>星期四</td><td>星期五</td><td>星期六</td><td>星期日</td></tr>"
    )
    empty_rows = "".join(
        "<tr><td>上午1-2节<br/>(01,02小节)<br/>08:00-09:40</td>"
        + "".join("<td></td>" for _ in range(7))
        + "</tr>"
        for _ in range(6)
    )
    return "<table id='tab1' class='kb_table'>" + header + empty_rows + "</table>"


def _expected_encoded(username: str, password: str, scode: str, sxh: str) -> str:
    code = username + "%%%" + password
    encoded = ""
    sxh_list = [int(x) for x in sxh]

    for i in range(len(code)):
        if i < len(sxh_list):
            encoded += code[i] + scode[0 : sxh_list[i]]
            scode = scode[sxh_list[i] :]
        else:
            encoded += code[i:]
            break
    return encoded


def test_login_and_get_schedule_does_not_exit_if_ddddocr_missing():
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ddddocr":
            raise ImportError("missing ddddocr for test")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        with patch("sys.exit", side_effect=AssertionError("sys.exit called")):
            reloaded = importlib.reload(crawler)

    result, err = reloaded.login_and_get_schedule("u", "p")
    assert result is None
    assert err is not None
    assert "ddddocr" in err.lower()
