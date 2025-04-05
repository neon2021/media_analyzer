#!/bin/bash

# 设置错误处理
set -e  # 遇到错误则退出
trap 'echo "测试失败，退出"; exit 1' ERR

# 确保测试环境设置
echo "======== 设置测试环境 ========"

# 设置PYTHONPATH
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# 确保脚本是可执行的
chmod +x media_analyzer/tests/unit/test_db_connection.py

# 检查Docker是否在运行中
echo "检查PostgreSQL容器状态..."
if docker ps | grep media_analyzer_postgres > /dev/null; then
    echo "PostgreSQL容器正在运行"
else
    echo "PostgreSQL容器未运行，启动容器..."
    docker-compose up -d
    # 等待容器启动
    echo "等待PostgreSQL容器启动..."
    sleep 10
fi

# 创建PostgreSQL测试数据库
echo "创建测试数据库..."
docker exec media_analyzer_postgres psql -U postgres -c "DROP DATABASE IF EXISTS media_analyzer_test;"
docker exec media_analyzer_postgres psql -U postgres -c "CREATE DATABASE media_analyzer_test WITH OWNER postgres;"

# 测试数据库连接
echo -e "\n======== 测试数据库连接 ========"
python media_analyzer/tests/unit/test_db_connection.py --config config/config-media-analyzer-test.yaml

# 使用测试配置运行测试
echo -e "\n======== 运行单元测试 ========"
python -m unittest media_analyzer/tests/unit/test_db_sync.py --config config/config-media-analyzer-test.yaml

# 测试结果
TEST_RESULT=$?

# 清理测试数据库
echo -e "\n======== 清理测试环境 ========"
docker exec media_analyzer_postgres psql -U postgres -c "DROP DATABASE IF EXISTS media_analyzer_test;"

# 处理测试结果
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "\n✅ 测试成功完成!"
    exit 0
else
    echo -e "\n❌ 测试失败，请检查日志!"
    exit 1
fi 