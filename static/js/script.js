const times = [
    '上午 1-2节|08:00-09:40',
    '上午 3-4节|10:00-11:40',
    '下午 5-6节|14:00-15:40',
    '下午 7-8节|16:00-17:40',
    '晚上 9-10节|18:30-20:10',
    '晚上 11节|20:20-21:05'
];
const colors = ['pink', 'blue', 'yellow', 'purple', 'green'];

function extractLocationCode(loc) {
    if (!loc) return '';
    const match = loc.match(/^[A-Za-z0-9]+/);
    return match ? match[0] : loc;
}

async function fetchSchedule(week) {
    const loading = document.getElementById('loading');
    const errorDiv = document.getElementById('error-msg');
    const timetable = document.getElementById('timetable');

    loading.style.display = 'flex';
    errorDiv.style.display = 'none';

    // Clear existing courses but keep headers
    const headers = Array.from(timetable.children).slice(0, 8);
    timetable.innerHTML = '';
    headers.forEach(h => timetable.appendChild(h));

    try {
        // 构建查询参数，包含周末标志
        let url = '/api/schedule';
        if (week) {
            url += `?week=${week}`;
        }
        
        // 如果是周末且没有指定周次，传递周末标志
        if (typeof isWeekendFromServer !== 'undefined' && isWeekendFromServer && !week) {
            url += (week ? '&' : '?') + 'is_weekend=true';
        }
        
        const response = await fetch(url);
        const data = await response.json();

        if (data.error) {
            document.getElementById('error-text').innerText = data.error;
            errorDiv.style.display = 'block';
            return;
        }

        // 显示周末提示
        if (data.weekend_message) {
            showWeekendNotification(data.weekend_message);
        }

        updateUI(data);
    } catch (e) {
        console.error(e);
        document.getElementById('error-text').innerText = '网络请求失败';
        errorDiv.style.display = 'block';
    } finally {
        loading.style.display = 'none';
    }
}

function showWeekendNotification(message) {
    // 创建并显示周末提示
    let notification = document.getElementById('weekend-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'weekend-notification';
        notification.className = 'weekend-notification';
        document.body.insertBefore(notification, document.body.firstChild);
    }
    
    notification.textContent = message;
    notification.style.display = 'block';
    
    // 3秒后自动隐藏
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

function updateDateStrip() {
    // 更新移动端日期导航栏
    const today = new Date();
    const currentDay = today.getDay(); // 0=周日, 1=周一, ...

    // 计算本周一的日期
    const monday = new Date(today);
    const diff = currentDay === 0 ? -6 : 1 - currentDay; // 如果是周日,退6天,否则计算到周一
    monday.setDate(today.getDate() + diff);

    // 更新7天的日期
    const dateItems = document.querySelectorAll('.date-item');
    dateItems.forEach((item, index) => {
        const date = new Date(monday);
        date.setDate(monday.getDate() + index);

        const dateNum = date.getDate();
        item.querySelector('.date-num').textContent = dateNum;

        // 高亮今天
        if (date.toDateString() === today.toDateString()) {
            item.classList.add('today');
        } else {
            item.classList.remove('today');
        }
    });
}

function updateUI(data) {
    document.getElementById('semester-info').innerText = data.semester_info || '';
    document.getElementById('generated-at').innerText = '生成时间: ' + data.generated_at;

    // 更新日期导航栏
    updateDateStrip();

    const gridContainer = document.getElementById('timetable');

    // Render slots
    for (let timeIdx = 0; timeIdx < 6; timeIdx++) {
        // Time label
        const timeSlot = document.createElement('div');
        timeSlot.className = 'time-slot';
        const parts = times[timeIdx].split('|');
        timeSlot.innerHTML = `<span>${parts[1]}</span><span style="font-size: 0.7rem; font-weight: normal;">${parts[0]}</span>`;
        gridContainer.appendChild(timeSlot);

        for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
            const key = `${timeIdx}-${dayIdx}`;
            const courses = data.grid[key];
            const delay = (timeIdx * 7 + dayIdx) * 0.03; // Stagger animation

            if (courses && courses.length > 0) {
                courses.forEach(course => {
                    const el = document.createElement('div');
                    el.className = `course animate-in ${colors[(timeIdx + dayIdx) % 5]}`;
                    el.style.animationDelay = `${delay}s`;

                    // Tooltip - 显示周次和教师
                    if (course.weeks || course.teacher) {
                        const tooltip = document.createElement('div');
                        tooltip.className = 'course-tooltip';
                        let tooltipText = '';
                        if (course.weeks) tooltipText += '📅 ' + course.weeks;
                        if (course.teacher) {
                            if (tooltipText) tooltipText += ' | ';
                            tooltipText += '👤 ' + course.teacher;
                        }
                        tooltip.innerText = tooltipText;
                        el.appendChild(tooltip);
                    }

                    // Name with code
                    const name = document.createElement('div');
                    name.className = 'course-name';
                    name.innerText = course.name + (course.code ? ' ' + course.code : '');
                    el.appendChild(name);

                    // Detail - 只显示地点
                    const detail = document.createElement('div');
                    detail.className = 'course-detail';
                    if (course.location) {
                        detail.innerHTML = `📍 ${extractLocationCode(course.location)}`;
                    }
                    el.appendChild(detail);

                    gridContainer.appendChild(el);
                });
            } else {
                const el = document.createElement('div');
                el.className = 'course empty animate-in';
                el.style.animationDelay = `${delay}s`;
                gridContainer.appendChild(el);
            }
        }
    }
}

function changeWeek() {
    const week = document.getElementById('weekSelect').value;
    fetchSchedule(week);
}

// Initial load
window.onload = () => {
    const urlParams = new URLSearchParams(window.location.search);
    // If URL has week param, use it, otherwise use the select value (which defaults to current or empty)
    let week = urlParams.get('week');
    if (!week) {
        week = document.getElementById('weekSelect').value;
    }
    fetchSchedule(week);
};
