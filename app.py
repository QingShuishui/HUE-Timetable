
import sys
import os
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

sys.stdout.reconfigure(encoding='utf-8')
from flask import Flask, render_template, request, jsonify
from PIL import Image

# Pillow 兼容性修复
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from config import DEBUG, HOST, PORT
from utils.crawler import login_and_get_schedule
from utils.parser import get_current_week, parse_weeks, extract_location_code, get_next_week

app = Flask(__name__)


app.jinja_env.filters['extract_location_code'] = extract_location_code


@app.route('/api/schedule')
def get_schedule_api():
    print('正在获取课表(API)...')
    data, error = login_and_get_schedule()
    
    current_week = get_current_week()
    
    if error:
        return jsonify({'error': error})
    
    week_param = request.args.get('week')
    is_weekend = request.args.get('is_weekend') == 'true'
    
    if week_param == 'current':
        week_param = current_week
    elif week_param:
        week_param = int(week_param)
    else:
        week_param = current_week
    
    # 如果是周末，自动跳转到下一周
    weekend_message = None
    if is_weekend and week_param == current_week:
        next_week = get_next_week()
        if next_week and next_week != current_week:
            week_param = next_week
            weekend_message = f"当前为周末，为您显示第 {next_week} 周课表"
        
    filtered_courses = []
    for course in data['courses']:
        if week_param is None:
            filtered_courses.append(course)
        else:
            course_weeks = parse_weeks(course.get('weeks', ''))
            if week_param in course_weeks:
                filtered_courses.append(course)
                
    grid = {}
    for course in filtered_courses:
        key = f"{course['row']}-{course['col']}"
        if key not in grid:
            grid[key] = []
        grid[key].append(course)
        
    return jsonify({
        'semester_info': data['semester_info'],
        'generated_at': data['generated_at'],
        'grid': grid,
        'current_week': current_week,
        'selected_week': week_param,
        'weekend_message': weekend_message
    })


@app.route('/')
def index():
    """主页 - 显示课表框架"""
    from datetime import datetime
    current_week = get_current_week()
    # 检查是否为周末
    today = datetime.now()
    weekday = today.weekday()  # 0=周一, 5=周六, 6=周日
    is_weekend = weekday >= 5  # 周六或周日
    return render_template('index.html', current_week=current_week, selected_week=current_week, is_weekend=is_weekend)


if __name__ == '__main__':
    print('=' * 60)
    print('简约课表系统 - 2026春季学期')
    print('=' * 60)
    print(f'访问地址: http://localhost:{PORT}')
    print('每次刷新页面都会实时获取最新课表')
    print(f'学期开始日期: 2026-03-02 (当前周次: {get_current_week() or "未开学"})')
    print('=' * 60)
    print()
    
    app.run(debug=DEBUG, host=HOST, port=PORT)
