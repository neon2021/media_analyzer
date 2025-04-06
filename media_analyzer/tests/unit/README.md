# 单元测试说明

本目录包含 Media Analyzer 的单元测试。

## 测试环境设置

运行测试前，请确保:

1. PostgreSQL 数据库已启动 (`docker-compose up -d`)
2. 测试配置文件存在 (`config/config-media-analyzer-test.yaml`)
3. 已安装必要的依赖 (`pip install tabulate`)

## 运行测试

可以使用以下命令运行所有单元测试:

```bash
python -m unittest discover media_analyzer/tests/unit
```

或者运行特定的测试:

```bash
python -m unittest media_analyzer/tests/unit/test_path_converter.py
```

## 文件扫描和PostgreSQL存储测试

`test_file_scan_postgres.py` 测试扫描本地文件、存储到PostgreSQL，并验证能够还原完整路径并打开文件。

### 数据库设计

该测试创建以下数据库表结构:

1. **devices表**: 存储设备信息
   - 主键: `id`
   - 唯一约束: `(uuid, system_id)` - 允许同一设备在不同系统上有不同的挂载点
   - 关键字段: `uuid`, `mount_path`, `system_id`, `first_seen`, `last_seen`

2. **files表**: 存储文件信息
   - 主键: `id`
   - 唯一约束: `(device_uuid, path, system_id)` - 允许同一设备在不同系统上有相同路径的文件
   - 关键字段: `device_uuid`, `path`, `hash`, `size`, `modified_time`, `system_id`

### 测试方式

1. **使用模拟文件** (默认):

   ```bash
   python media_analyzer/tests/unit/test_file_scan_postgres.py
   ```
   
   此方式会创建临时目录和测试文件。

2. **使用真实目录中的文件**:

   ```bash
   python media_analyzer/tests/unit/test_file_scan_postgres.py --real_scan_dir="/path/to/your/directory"
   ```
   
   此方式会扫描指定目录中的不超过3个媒体文件。

3. **保留数据库表供后续使用**:

   ```bash
   python media_analyzer/tests/unit/test_file_scan_postgres.py --keep_tables
   ```
   
   默认情况下，测试会在完成后删除创建的数据库表。使用 `--keep_tables` 参数可以保留这些表，以便您可以使用 `show_db_tables.py` 脚本查看其内容。
   
   使用此选项时，测试会额外创建一个相同UUID但不同系统ID的设备记录，以演示系统对同一设备在不同系统上的处理能力。

### 表格输出

测试运行时会在命令行中以表格形式显示以下信息:

1. **设备表** - 显示已创建的设备记录，包括UUID、挂载路径和系统ID等信息
2. **文件表** - 显示存储到数据库中的文件记录，包括路径、哈希值、大小和时间戳等信息
3. **已还原文件** - 显示成功还原和打开的文件信息，包括文件ID、相对路径、完整路径和状态
4. **相同设备在不同系统上** - 显示使用相同UUID但不同system_id的设备记录(当使用`--keep_tables`选项时)

表格格式化使用 `tabulate` 库来提供清晰的输出格式。

### 查看数据库表内容

使用 `--keep_tables` 参数运行测试后，可以使用以下命令查看数据库表内容:

```bash
python media_analyzer/scripts/show_db_tables.py --config config/config-media-analyzer-test.yaml
```

该脚本支持以下选项:
- `--device UUID` - 指定设备UUID查看其文件
- `--system SYSTEM_ID` - 指定系统ID查看其设备和文件
- `--limit N` - 限制显示的记录数量（默认10条）
- `--all` - 显示所有记录（不限制数量）
- `--summary` - 仅显示设备概要信息

例如，要查看特定系统上的特定设备:

```bash
python media_analyzer/scripts/show_db_tables.py --device test_123456 --system macos-myhost
```

### 注意事项

- 测试会自动创建和清理所需的数据库表（除非使用 `--keep_tables` 参数）
- 使用真实目录时，不会修改您的文件，仅读取它们的内容
- 确保PostgreSQL数据库配置正确，测试使用的是 `config/config-media-analyzer-test.yaml` 中的配置
- 系统现在支持同一设备UUID在不同system_id上的情况，这适用于外接存储设备在多台计算机间移动的场景 