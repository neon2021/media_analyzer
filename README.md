# Media Analyzer

媒体文件分析工具，用于跟踪和管理多个外部设备上的媒体文件。

## 功能特点

- 扫描并索引外部设备上的媒体文件
- 自动检测和管理设备挂载
- 支持多系统环境下的设备识别
- 使用PostgreSQL数据库存储文件元数据
- 提供命令行工具进行文件搜索和管理

## 安装说明

### 安装依赖

```bash
# 使用pip安装
pip install -e .

# 或使用requirements.txt
pip install -r requirements.txt
```

### 数据库设置

项目使用PostgreSQL数据库存储文件元数据。可以通过Docker快速设置PostgreSQL:

```bash
docker-compose up -d postgres
```

数据库表结构自动创建，主要包含:

- `devices`: 存储设备信息，包含UUID和挂载点
  - 设备表使用(`uuid`, `system_id`)作为联合唯一索引，允许同一设备在不同系统上使用
- `files`: 存储文件元数据，包含路径、大小、哈希值等

## 配置

项目使用YAML配置文件，配置文件位置可以是:

- `./config-media-analyzer.yaml` (当前目录)
- `~/config-media-analyzer.yaml` (用户主目录)
- `./config/config-media-analyzer.yaml` (config子目录)
- `~/.config/media-analyzer/config.yaml` (系统配置目录)

可以复制`config/config-template.yaml`并根据需要修改:

```yaml
# 系统配置
system:
  id: "auto"  # 系统ID，设置为"auto"会根据主机名和系统类型自动生成

# 数据库配置
database:
  # SQLite配置
  path: "media_analyzer.db"  # SQLite数据库文件路径
  
  # PostgreSQL配置
  postgres:
    host: "localhost"  # 数据库主机名
    port: 5432  # 端口号
    database: "media_analyzer"  # 数据库名称
    username: "postgres"  # 用户名
    password: "postgres"  # 密码

# 扫描配置
scan:
  hash_timeout: 10  # 单个文件哈希计算超时时间（秒）
  progress_interval: 30  # 进度报告间隔（秒）
  skip_dirs:  # 扫描时跳过的目录
    - "/System"
    - "/Volumes/Recovery"
    # ...更多跳过目录
```

## 使用方法

### 启用db回退和不回退

```bash
ALLOW_DB_FALLBACK=true PYTHONPATH=.../media_analyzer:$PYTHONPATH python main-002-scan_files.py | cat
```

```bash
ALLOW_DB_FALLBACK=false PYTHONPATH=.../media_analyzer:$PYTHONPATH python main-002-scan_files.py | cat
```

### 列出设备

```bash
python -m media_analyzer.main --list-devices
```

### 更新设备注册表

```bash
python -m media_analyzer.main --update-registry
```

### 扫描设备

```bash
python -m media_analyzer.main --scan /Volumes/MyExternalDrive
```

### 数据库查询示例

```bash
python -m media_analyzer.scripts.show_db_tables
```

## 开发

### 代码结构

- `media_analyzer/`: 主程序包
  - `core/`: 核心功能模块
  - `db/`: 数据库操作
  - `scripts/`: 命令行脚本
  - `utils/`: 工具函数

### 测试

```bash
# 运行单元测试
pytest media_analyzer/tests/unit

# 运行集成测试
pytest media_analyzer/tests/integration
```

## 许可证

本项目采用MIT许可证。详情请参阅LICENSE文件。

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

#### 自动配置（推荐）

我们提供了一个自动化脚本，可以根据不同操作系统自动选择适合的数据库配置。这个脚本会自动检测您的操作系统，根据配置文件生成合适的 Docker Compose 配置，并启动 PostgreSQL 服务。

```bash
# 自动检测操作系统并启动数据库服务
python scripts/db_setup.py

# 使用测试配置
python scripts/db_setup.py --test

# 指定自定义配置文件
python scripts/db_setup.py --config path/to/your/config.yaml

# 如果需要，可以强制使用特定操作系统的配置
python scripts/db_setup.py --os macos
python scripts/db_setup.py --os linux
python scripts/db_setup.py --os windows

# 停止数据库服务
python scripts/db_setup.py --stop

# 重启数据库服务
python scripts/db_setup.py --restart
```

数据库连接信息会根据配置文件自动确定，默认为:
- 主机: localhost
- 端口: 5433
- 用户名: postgres
- 密码: postgres
- 数据库: media_analyzer

#### 配置文件中的Docker设置

您可以在配置文件中自定义不同操作系统下的Docker设置。以下是一个示例:

```yaml
database:
  # 其他数据库设置...
  docker:
    # 所有平台通用的设置
    common:
      port: 5433  # 映射到主机的端口
      username: postgres
      password: postgres
      database: media_analyzer
      container_name: postgres-db
    # macOS专用设置
    macos:
      version: '3.8'
      build_context: true  # 使用Dockerfile构建还是直接使用镜像
      image: postgres:14
      healthcheck: true    # 是否启用健康检查
      volume_name: postgres_data
    # Linux专用设置  
    linux:
      version: '3'
      build_context: false
      image: postgres:14
      healthcheck: false
      volume_name: postgres-data
      env_vars_format: direct  # 环境变量格式 (direct或template)
```

当您运行`db_setup.py`脚本时，它会根据您的操作系统选择相应的配置，生成适合的`docker-compose.yml`文件。

#### macOS 手动配置

系统支持使用PostgreSQL存储数据。使用Docker运行数据库：

```bash
docker-compose up -d
```

#### Ubuntu 手动配置

在Ubuntu上安装PostgreSQL有两种方式：本地安装或Docker安装。

##### 方式一：本地安装PostgreSQL

```bash
# 更新包索引
sudo apt update

# 安装PostgreSQL及相关工具
sudo apt install postgresql postgresql-contrib -y

# 设置postgres用户密码
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"

# 修改认证方式从scram-sha-256为md5
sudo sed -i 's/scram-sha-256/md5/g' /etc/postgresql/14/main/pg_hba.conf

# 重启PostgreSQL服务
sudo systemctl restart postgresql

# 创建应用数据库
sudo -u postgres psql -c "CREATE DATABASE media_analyzer_test;"
```

##### 方式二：使用Docker安装PostgreSQL

```bash
# 安装Docker和Docker Compose
sudo apt update
sudo apt install docker.io docker-compose -y

# 添加当前用户到docker组（需要重新登录才能生效）
sudo usermod -aG docker $USER

# 解决Docker网络连接问题
echo '{"dns": ["8.8.8.8", "8.8.4.4"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker

# 创建Docker Compose配置
mkdir -p ~/docker-postgres
cd ~/docker-postgres

cat > docker-compose.yml << EOF
version: '3'

services:
  postgres:
    image: postgres:14
    container_name: postgres-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: media_analyzer_test
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres-data:
EOF

# 启动PostgreSQL容器
sudo docker-compose up -d

# 或者直接使用docker命令
sudo docker run --name postgres-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=media_analyzer_test \
  -p 5433:5432 \
  -d postgres:14
```

##### Docker常用命令

```bash
# 查看容器状态
docker ps

# 查看容器日志
docker logs postgres-db

# 执行SQL命令
docker exec -it postgres-db psql -U postgres -d media_analyzer_test -c "SELECT version();"

# 获取交互式PostgreSQL shell
docker exec -it postgres-db psql -U postgres -d media_analyzer_test

# 停止容器
docker stop postgres-db

# 删除容器
docker rm postgres-db
```

注意：如果使用Docker安装，需要在配置文件中设置端口为5433：

```yaml
database:
  postgres:
    host: localhost
    port: 5433  # 从默认的5432改为5433
    database: media_analyzer_test
    username: postgres
    password: postgres
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

