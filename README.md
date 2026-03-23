# HUE Timetable

一个为 HUE 教务系统设计的轻量课表查看器：
后端使用 Flask 实时拉取课表，前端以卡片化网格展示，支持按周筛选并在周末自动跳转到下一周。

---

## 项目亮点

- 实时获取：每次刷新页面都会重新拉取教务系统数据
- 智能周次：根据开学日期自动计算当前周
- 周末优化：周末访问可自动展示下一周课表
- 课程聚合：同一时间段多门课程可并排展示
- 移动端适配：包含移动端日期条与底部导航样式
- 轻依赖：基于 requests + BeautifulSoup + ddddocr

## 技术栈

- Python / Flask
- requests
- BeautifulSoup4 + lxml
- ddddocr（验证码识别）
- Pillow
- HTML + CSS + Vanilla JavaScript

## 目录结构

```text
kcb2/
├─ app.py                 # Flask 应用入口
├─ config.py              # 账号、学期、服务配置
├─ requirements.txt       # Python 依赖
├─ static/
│  ├─ css/style.css       # 页面样式
│  └─ js/script.js        # 前端交互逻辑
├─ templates/
│  └─ index.html          # 页面模板
└─ utils/
   ├─ crawler.py          # 登录与课表抓取
   └─ parser.py           # 课表与周次解析
```

## 快速开始

### 1. 克隆并进入项目

```bash
git clone https://github.com/QingShuishui/HUE-Timetable.git
cd HUE-Timetable
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置账号信息

编辑 `config.py`：

```python
USERNAME = '你的学号'
PASSWORD = '你的密码-默认出生日期'
BASE_URL = 'https://jwxt.hue.edu.cn'

SEMESTER_START_DATE = '2026-03-02'

DEBUG = True
HOST = '0.0.0.0'
PORT = 5004
```

### 4. 启动服务

```bash
python app.py
```

浏览器访问：

```text
http://localhost:5004
```

## API 说明

### `GET /api/schedule`

获取课表数据（JSON）。

#### 查询参数

- `week`：周次（如 `1`、`2`、`current`）
- `is_weekend`：`true/false`，用于周末自动跳转逻辑

#### 返回字段（简化）

- `semester_info`：学期信息
- `generated_at`：生成时间
- `grid`：按 `row-col` 组织的课程网格
- `current_week`：当前周
- `selected_week`：当前筛选周
- `weekend_message`：周末提示信息

## 配置项说明

`config.py` 主要配置：

- `USERNAME` / `PASSWORD`：教务系统登录账号
- `BASE_URL`：教务系统根地址
- `SEMESTER_START_DATE`：用于计算当前周次
- `TIME_SLOTS`：时间段展示文本
- `WEEKDAYS`：星期展示文本
- `HOST` / `PORT` / `DEBUG`：Flask 启动参数

## 常见问题

### 1. 登录失败

- 检查 `USERNAME` 和 `PASSWORD` 是否正确
- 学校教务系统可能临时不可用，请稍后重试
- 若验证码识别连续失败，可多刷新几次

### 2. 依赖安装报错

可先升级 pip 再安装：

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 端口被占用

修改 `config.py` 中的 `PORT`（例如改为 `5005`）后重启。

## 安全建议

- 不要将真实账号密码提交到仓库
- 建议本地开发时通过环境变量或本地配置覆盖敏感信息

