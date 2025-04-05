FROM postgres:14

# 创建初始化脚本目录
RUN mkdir -p /docker-entrypoint-initdb.d
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d
RUN chmod 755 /docker-entrypoint-initdb.d

# 复制初始化脚本
COPY init-scripts/01-init.sql /docker-entrypoint-initdb.d/
RUN chown postgres:postgres /docker-entrypoint-initdb.d/01-init.sql
RUN chmod 644 /docker-entrypoint-initdb.d/01-init.sql

# 设置工作目录
WORKDIR /docker-entrypoint-initdb.d

# 使用 postgres 用户
USER postgres 