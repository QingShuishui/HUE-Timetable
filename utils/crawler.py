#!/usr/bin/env python3
"""
爬虫模块 - 负责登录教务系统并获取课表数据
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

try:
    import ddddocr
except ImportError:
    ddddocr = None

from config import BASE_URL, SEMESTER_START_DATE, TIME_SLOTS, WEEKDAYS
from utils.parser import parse_table


FALLBACK_WEEK_COUNT = 20
FALLBACK_DAYS_PER_WEEK = 7
FALLBACK_MAX_WORKERS = 20


def login_and_get_schedule(username, password, semester_start_date=SEMESTER_START_DATE):
    """登录并获取课表数据"""
    if ddddocr is None:
        return None, "未安装 ddddocr 库，请先安装后再试"

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    # 1. 访问首页
    session.get(BASE_URL, timeout=10)

    # 2. 获取加密参数
    r = session.get(f'{BASE_URL}/Logon.do?method=logon&flag=sess', timeout=10)
    if '#' not in r.text:
        return None, "获取加密参数失败"

    scode, sxh = r.text.split('#')

    # 3. 识别验证码
    r = session.get(f'{BASE_URL}/verifycode.servlet', timeout=10)
    try:
        ocr = ddddocr.DdddOcr()
        captcha = ocr.classification(r.content)
    except Exception as e:
        return None, f"验证码识别失败: {e}"

    # 4. 生成加密凭据
    code = username + '%%%' + password
    encoded = ''
    sxh_list = [int(x) for x in sxh]

    for i in range(len(code)):
        if i < len(sxh_list):
            encoded += code[i] + scode[0:sxh_list[i]]
            scode = scode[sxh_list[i]:]
        else:
            encoded += code[i:]
            break

    # 5. 提交登录
    r = session.post(
        f'{BASE_URL}/Logon.do?method=logon',
        data={'useDogCode': '', 'encoded': encoded, 'RANDOMCODE': captcha},
        allow_redirects=True,
        timeout=10
    )

    if 'xsMain.jsp' not in r.url:
        if '验证码错误' in r.text:
            return login_and_get_schedule(username, password, semester_start_date)  # 验证码错误，重试
        return None, "登录失败"

    # 6. 获取课表
    schedule_url = f'{BASE_URL}/jsxsd/xskb/xskb_list.do'
    r = session.get(schedule_url, timeout=10)
    if r.status_code != 200:
        return None, "获取课表失败"

    soup = BeautifulSoup(r.text, 'html.parser')

    # 解析学期信息
    week_div = soup.find('div', {'id': 'timetableDiv'})
    semester_info = week_div.get_text(strip=True) if week_div else ''

    # 解析课表
    table = soup.find('table', {'id': 'kbtable'})
    if not table:
        return None, "未找到课表"

    courses = parse_table(table)
    if not courses:
        courses = _fetch_fallback_courses(session, semester_start_date)

    return {
        'semester_info': semester_info,
        'courses': courses,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, None


def _fetch_fallback_courses(session, semester_start_date):
    courses = []
    dates = list(_iter_fallback_dates(semester_start_date))

    with ThreadPoolExecutor(max_workers=FALLBACK_MAX_WORKERS) as executor:
        futures = [
            executor.submit(_fetch_weekly_fallback_courses, session, course_date, week)
            for course_date, week in dates
        ]
        for future in as_completed(futures):
            courses.extend(future.result())

    return _merge_course_weeks(courses)


def _iter_fallback_dates(semester_start_date):
    start_date = datetime.strptime(semester_start_date, '%Y-%m-%d').date()
    for week in range(1, FALLBACK_WEEK_COUNT + 1):
        course_date = start_date + timedelta(days=(week - 1) * FALLBACK_DAYS_PER_WEEK)
        yield course_date, week


def _fetch_weekly_fallback_courses(session, course_date, week):
    response = session.post(
        f'{BASE_URL}/jsxsd/framework/main_index_loadkb.jsp',
        data={'rq': course_date.strftime('%Y-%m-%d')},
        headers={'X-Requested-With': 'XMLHttpRequest'},
        timeout=10,
    )
    if response.status_code != 200:
        return []
    return _parse_fallback_week_courses(response.text, course_date, week)


def _parse_fallback_week_courses(html, course_date, week):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', {'id': 'kbtable'}) or soup.find('table')
    if not table:
        return []

    if _is_index_week_table(table):
        return _parse_index_week_table(table, week)

    force_day_from_date = _looks_like_daily_table(table)
    courses = []
    for course in parse_table(table):
        normalized = dict(course)
        if force_day_from_date:
            normalized['col'] = course_date.weekday()
            normalized['day'] = WEEKDAYS[course_date.weekday()]
        normalized['weeks'] = f'{week}(周)'
        courses.append(normalized)
    return courses


def _looks_like_daily_table(table):
    rows = table.find_all('tr')[1:]
    if not rows:
        return False
    max_cell_count = max((len(row.find_all('td')) for row in rows), default=0)
    return max_cell_count < len(WEEKDAYS)


def _is_index_week_table(table):
    classes = table.get('class', [])
    return table.get('id') == 'tab1' or 'kb_table' in classes


def _parse_index_week_table(table, week):
    courses = []
    rows = table.find_all('tr')[1:]

    for row_idx, row in enumerate(rows[:6]):
        cells = row.find_all(['td', 'th'])
        for day_idx, cell in enumerate(cells[1:8]):
            for item in cell.find_all(title=True):
                fields = _parse_course_title(item.get('title', ''))
                raw_name = fields.get('课程名称', '').strip()
                if not raw_name:
                    continue

                course_name, course_code = _split_course_name_and_code(raw_name)
                courses.append({
                    'name': course_name,
                    'code': course_code,
                    'teacher': _extract_teacher(fields),
                    'location': fields.get('上课地点', '').strip(),
                    'weeks': f'{week}(周)',
                    'time': _extract_time_slot(row_idx),
                    'day': WEEKDAYS[day_idx],
                    'row': row_idx,
                    'col': day_idx,
                })

    return courses


def _parse_course_title(title):
    title_text = BeautifulSoup(title, 'html.parser').get_text('\n')
    fields = {}
    for line in title_text.splitlines():
        line = line.strip()
        if '：' not in line:
            continue
        key, value = line.split('：', 1)
        fields[key.strip()] = value.strip()
    return fields


def _split_course_name_and_code(raw_name):
    if ' ' not in raw_name:
        return raw_name, ''

    name, maybe_code = raw_name.rsplit(' ', 1)
    if len(maybe_code) <= 6 and maybe_code.isupper() and not any(char.isdigit() for char in maybe_code):
        return name, maybe_code
    return raw_name, ''


def _extract_teacher(fields):
    for key in ('任课教师', '授课教师', '教师'):
        if fields.get(key):
            return fields[key].strip()
    return ''


def _extract_time_slot(row_idx):
    if row_idx < len(TIME_SLOTS):
        return TIME_SLOTS[row_idx]
    return ''


def _merge_course_weeks(courses):
    merged = {}
    key_fields = ('name', 'code', 'teacher', 'location', 'time', 'day', 'row', 'col')

    for course in courses:
        if not course.get('name'):
            continue

        key = tuple(course.get(field, '') for field in key_fields)
        if key not in merged:
            merged[key] = dict(course)
            merged[key]['_week_numbers'] = set()

        merged[key]['_week_numbers'].update(_parse_week_numbers(course.get('weeks', '')))

    result = []
    for course in merged.values():
        week_numbers = sorted(course.pop('_week_numbers'))
        course['weeks'] = _format_week_numbers(week_numbers)
        result.append(course)

    return sorted(result, key=lambda course: (course['row'], course['col'], course['name']))


def _parse_week_numbers(weeks):
    if not weeks:
        return []

    week_text = weeks.replace('(周)', '').strip()
    result = []
    for part in week_text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return result


def _format_week_numbers(week_numbers):
    if not week_numbers:
        return ''

    ranges = []
    start = previous = week_numbers[0]
    for week in week_numbers[1:]:
        if week == previous + 1:
            previous = week
            continue
        ranges.append(_format_week_range(start, previous))
        start = previous = week
    ranges.append(_format_week_range(start, previous))
    return ','.join(ranges) + '(周)'


def _format_week_range(start, end):
    if start == end:
        return str(start)
    return f'{start}-{end}'
