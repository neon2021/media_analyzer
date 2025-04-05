# Media Analyzer

媒体文件分析和管理系统，支持扫描、分析和搜索媒体文件。

## 项目结构

```
media_analyzer/
├── config/                  # 配置文件目录
│   ├── config-media-analyzer.yaml        # 主配置文件
│   └── config-media-analyzer-test.yaml   # 测试配置
├── media_analyzer/          # 主代码包
│   ├── api/                 # API 和界面
│   ├── core/                # 核心功能
│   ├── db/                  # 数据库交互
│   ├── models/              # 数据模型
│   ├── scripts/             # 入口脚本
│   ├── tests/               # 测试代码
│   └── utils/               # 工具类
├── scripts/                 # 辅助脚本
├── setup.py                 # 安装脚本
└── README.md                # 项目说明
```

## 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/media_analyzer.git
cd media_analyzer

# 安装依赖
pip install -e .
```

## 配置

复制并编辑配置文件：

```bash
cp config/config-media-analyzer.yaml ~/config-media-analyzer.yaml
# 编辑配置
nano ~/config-media-analyzer.yaml
```

## 使用方法

### 命令行工具

```bash
# 扫描媒体文件
media-scan --config ~/config-media-analyzer.yaml

# 分析媒体文件
media-analyze --config ~/config-media-analyzer.yaml --limit 100
```

### 从源码运行

```bash
# 扫描媒体文件
python -m media_analyzer.scripts.scan --config ~/config-media-analyzer.yaml

# 分析媒体文件
python -m media_analyzer.scripts.analyze --config ~/config-media-analyzer.yaml
```

## 开发

### 运行测试

```bash
# 运行所有测试
./scripts/run_tests.sh

# 或者
python -m unittest discover media_analyzer/tests
```

### 数据库

系统支持使用PostgreSQL存储数据。使用Docker运行数据库：

```bash
docker-compose up -d
```

```shell
conda activate tf-metal
```


```shell
pip install pillow exifread face_recognition torch torchvision
```

```shell
pip freeze | grep -Ei "pillow|exifread|face_recognition|torch|torchvision"

ExifRead==3.0.0
Pillow==10.0.0
torch==2.0.0
torchvision==0.15.1
```

## 准备：安装 YOLOv5 推理环境

```shell
pip install torch torchvision
pip install opencv-python

# 以下指令失败了
git clone https://github.com/ultralytics/yolov5.git
cd yolov5
pip install -r requirements.txt

# 在页面： https://github.com/ultralytics/yolov5/releases 下载 source zip: https://github.com/ultralytics/yolov5/archive/refs/tags/v7.0.zip

```

## 建表

```sql
CREATE TABLE IF NOT EXISTS image_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    camera_model TEXT,
    taken_time TEXT,
    gps_lat REAL,
    gps_lon REAL,
    has_faces INTEGER DEFAULT 0,
    objects TEXT,
    analyzed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

ALTER TABLE image_analysis ADD COLUMN objects TEXT;
```

## 安装UI开发组件

```shell
pip install streamlit
```

### 开发完毕 image_search_app.py 启动网页版 GUI

```shell
streamlit run image_search_app.py
```

