# Custom Report System - Backend

自定义报表查询系统后端服务。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

## 运行

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API 文档

启动服务后访问：http://localhost:8000/docs
