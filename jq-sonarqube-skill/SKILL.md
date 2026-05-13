---
name: jq-sonarqube-skill
description: >
  SonarQube 查询参考手册。当用户提到 SonarQube、代码扫描、代码问题、
  Sonar 问题、代码质量时使用。
  核心能力：问题统计、问题详情查询、规则修复建议。
triggers:
  - SonarQube
  - sonarqube
  - 代码扫描
  - 代码问题
  - Sonar 问题
  - 代码质量
  - 规则修复
metadata:
  category: devops-api
  tags: [sonarqube, code-quality]
---

# SonarQube 查询参考手册

## 快速导航

**不知道该用哪个命令？**

```
├─ 想了解项目的整体问题数量/分布
│   └─ stats <sonarkey>
├─ 想查具体问题列表（按 severity / type / status 过滤）
│   └─ issues <sonarkey> [--severity/--type/--status/--rule]
├─ 想了解某个规则本身的含义/修复方案
│   └─ rule <规则ID>
└─ 只有模块名，想一键查询（自动构造 SonarKey）
    └─ module <模块名> [--branch]
```

---

## 核心概念：SonarKey

### 构造公式

```
SonarKey = GitLab路径.replace('/', '_') + '_' + 分支名
```

### 构造示例

| 输入 | 分支 | SonarKey |
|------|------|---------|
| `enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service/gcreport-aidocaudit` | `dev` | `enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_gcreport-aidocaudit_dev` |
| `gcreport-center` | `dev`（默认） | `gcreport-center_dev` |

**未指定分支时默认取 `_dev`**。

### 常用分支后缀

| 分支 | 后缀 |
|------|------|
| dev | `_dev` |
| master | `_master` |
| 其他 | `_{分支名}` |

---

## 查询命令

### 1. stats — 统计摘要

```bash
python -m scripts.queries stats <sonarkey> [--no-cache]
```

**输出**：

```json
{
  "total": 1234,
  "by_severity": { "BLOCKER": 5, "CRITICAL": 42, "MAJOR": 156, "MINOR": 800, "INFO": 231 },
  "by_type": { "BUG": 89, "VULNERABILITY": 23, "CODE_SMELL": 1122 }
}
```

### 2. issues — 问题详情

```bash
python -m scripts.queries issues <sonarkey> [--severity MAJOR] [--type BUG] [--status OPEN] [--rule java:S3776]
```

**输出**：问题列表，每条含 `key`、`severity`、`type`、`message`、`rule`、`component`

**重要限制**：
- `--severity MAJOR` 为**精确过滤**。SonarQube API 不支持 `>=MAJOR`。查询 MAJOR 及以上需分 3 次查询，或直接查全部后人工筛选。
- `SonarKey` 未指定分支后缀时默认 `_dev`。

### 3. rule — 规则元数据

```bash
python -m scripts.queries rule java:S3776
```

**输出**：`descriptionSections` 字段，含 `how_to_fix`、`noncompliant code example`、`compliant solution`

> **区分**：`rule` 查的是规则的通用说明/修复方案；`issues --rule` 查的是某项目中的具体违规。

### 4. module — 统一入口（推荐）

```bash
python -m scripts.queries module <模块名> [--branch dev]
```

**执行流程**：

| 步骤 | 操作 | 输入 | 输出 |
|------|------|------|------|
| 1 | 从 GitLab 搜索模块路径 | `模块名`（GitLab 路径末段） | GitLab 完整路径 |
| 2 | 转换为 SonarKey | GitLab 路径 + 分支 | `SonarKey` |
| 3 | 查询统计摘要 + 问题详情 | `SonarKey` | 统计摘要 + 问题列表 |

### 5. 缓存控制

```bash
python -m scripts.queries clear <sonarkey>      # 清除指定缓存
python -m scripts.queries clear --all          # 清除全部缓存
python -m scripts.queries clear-sonarkey        # 清除 SonarKey 映射缓存
python -m scripts.queries cleanup               # 清理过期缓存
```

### 6. 预热与预取

```bash
python -m scripts.queries warm --file queries.json
python -m scripts.queries prefetch <sonarkey> --types stats,issues
```

---

## 执行检查点

> 关键操作前须确认，防止自主失控。

| 时机 | 确认内容 |
|------|---------|
| SonarKey 构造后 | 路径是否正确、分支后缀是否符合预期（默认 `_dev`） |
| 执行 `module` 查询前 | 确认模块名为 GitLab 路径末段、分支是否为目标分支（`--branch dev/master`） |

---

## 配置与凭证

配置文件搜索路径（优先级）：`./jq-config.json` → `<skill>/jq-config.json` → `../jq-config.json`

```json
{
  "gitlab": {
    "token": "glpat_xxxxxxxxxxxx",
    "base_url": "https://nvwa.jiuqi.com.cn/gitlab/api/v4"
  },
  "sonarqube": {
    "token": "squ_xxxxxxxxxxxx",
    "base_url": "https://nvwa.jiuqi.com.cn/sonar/api"
  }
}
```

**Token 获取方式**：
- `gitlab.token`：GitLab → Settings → Access Tokens
- `sonarqube.token`：SonarQube → My Account → Security

---

## 缓存机制

| 类型 | TTL | 说明 |
|------|-----|------|
| 查询结果 | 1h | 相同 sonarkey + 查询类型 + filters 的请求返回缓存 |
| 模块映射 | 7d | GitLab 路径 → SonarKey 转换结果复用 |
| Stale 刷新 | 过期前 10min | 立即返回旧数据 + 后台异步刷新（用户无感知） |

### 已处理问题标记

```bash
# 标记问题为已处理
python -c "from scripts.cache import QueryCache; QueryCache().mark_processed('sonarkey', ['issue_key1', 'issue_key2'])"

# 取消标记
python -c "from scripts.cache import QueryCache; QueryCache().unmark_processed('sonarkey', ['issue_key1'])"
```

查询结果中带 `processed_keys` 字段，标识已处理的问题。

---

## 错误处理

| 场景 | 原因 | 处理 |
|------|------|------|
| 返回空结果 | 项目无问题 / 筛选条件过严 | 先不加过滤查询 |
| 401 Unauthorized | Token 过期 | 检查 `jq-config.json` |
| 404 Not Found | SonarKey 不存在 | 验证 SonarKey 构造是否正确 |
| 分页数据 | 结果超 100 条 | 自动分页，拉取所有页 |
| 超时/网络错误 | SonarQube 不可达 | 重试 1 次，失败则报错 |
