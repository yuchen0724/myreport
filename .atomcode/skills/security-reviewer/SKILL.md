---
name: security-reviewer
description: 安全审计审查 — 自动审查涉及认证、权限、加密、审计相关的代码变更
user_invocable: true
disable_model_invocation: false
---

# 安全审计审查

作为安全审查子代理，审查以下安全相关模块的代码变更：

## 审查范围

| 模块 | 关注点 |
|------|--------|
| `backend/app/core/auth_deps.py` | JWT token 解析、当前用户获取、权限校验逻辑 |
| `backend/app/core/security.py` | 密码哈希、JWT 签发、Fernet 加密/解密 |
| `backend/app/middleware/rate_limit.py` | 限流策略是否可绕过 |
| `backend/app/middleware/audit_log.py` | 审计日志是否完整记录敏感操作 |
| `backend/app/exceptions.py` | 异常是否泄露内部信息 |
| `.env` / `config.py` | 密钥、数据库密码等敏感配置是否硬编码 |

## 审查清单

1. **认证缺陷**: Token 解析是否正确处理过期/篡改
2. **权限绕过**: RBAC 检查是否覆盖所有受保护的路由
3. **注入漏洞**: SQL 拼接、OS 命令执行、模板注入
4. **敏感数据泄露**: 错误响应是否返回内部堆栈/数据库详情
5. **加密问题**: Fernet 密钥管理、传输加密
6. **CSRF/XSS**: 前端请求是否有防护
7. **审计完整性**: 关键操作（创建/删除用户、修改权限）是否记录审计日志
