---
name: jq-sonarqube-skill
description: >
  SonarQube 查询参考手册。当用户提到 SonarQube、代码扫描、代码问题、
  Sonar 问题、代码质量时使用。
  核心能力：问题统计、问题详情查询、规则修复建议、Build 验证。
metadata:
  category: devops-api
  tags: [sonarqube, code-quality]
---

# SonarQube 查询参考手册

## TL;DR

> **重要**：调用此 skill 时，**必须使用 subagent 方式**执行查询/修复/验证操作，主 agent 只负责任务分发。

| 任务类型 | 触发场景 | 执行方式 |
|---------|---------|---------|
| 查询类 | 统计摘要、问题详情、规则详情 | **subagent**: 查询 {target} 的 {统计/问题/规则} |
| 修复类 | 修复建议、代码方案 | **subagent**: 修复 {SonarKey} 的 {规则} 问题 |
| 验证类 | Build 验证 | **subagent**: 验证 {module} 的 Build |

| 需求 | subagent 指令 |
|------|--------------|
| 模块名查询 | 先查 GitLab 路径，再构造 SonarKey（见第0步） |
| 快速看统计 | `subagent: 查询 {module} 的 Sonar 统计` |
| 查具体问题 | `subagent: 查询 {SonarKey} 的 OPEN+{severity}+{type} 问题` |
| 修复建议 | `subagent: 查询 java:S{编号} 规则的修复建议` |
| Build 验证 | `subagent: 验证 {module} 的 Build` |
| SonarKey 构造 | 路径 `/` 改 `_` + 末尾加 `_dev` | 详见"三步转换法"

## 概述

此 skill 所有操作**必须通过 subagent 执行**，主 agent 不直接调用 SonarQube API。

## Subagent 任务分发规则

**重要**：一个任务类型只创建一个 subagent，同一类型的多个请求合并到一个 subagent 中执行。

| 任务类型 | 触发场景 | subagent 任务描述 |
|---------|---------|------------------|
| **查询类** | 用户请求统计/问题详情/规则详情 | `subagent: 查询 {target} 的 {统计/问题/规则}` |
| **修复类** | 用户请求规则修复建议、代码方案 | `subagent: 修复 {SonarKey} 的 {规则} 问题` |
| **验证类** | 用户请求 Build 验证 | `subagent: 验证 {module} 的 Build` |

### 执行流程

```
用户请求
   ↓
主 agent 识别任务类型
   ↓
创建对应类型的 subagent（每个类型最多 1 个）
   ↓
subagent 执行 SonarQube API 调用
   ↓
结果返回主 agent 汇总
```

**检查点**：执行任何查询前，先确认 Sonar Key 是否正确。Sonar Key 填错将返回 404，但 skill 不会自动提示。

**推荐工作流**：
1. **查 GitLab 路径**（用户提供模块名时）→ 构造 SonarKey
2. **查询类 subagent** → 查统计摘要
3. 按需**查询类 subagent** → 查问题详情
4. **修复类 subagent** → 获取修复建议
5. **验证类 subagent** → Build 验证

## 0. 模块名→GitLab路径（当用户提供模块名时）

### 场景

用户说"查询 gcreport-jra 的问题"（而非完整 SonarKey）

### 方式一：从本地代码获取（推荐）

当模块在本地存在时，直接从 `.git/config` 读取路径，最准确：

```bash
cat {module_dir}/.git/config
```

**提取 `url` 字段**，格式为 `https://nvwa.jiuqi.com.cn/gitlab/{path}.git`

取中间部分即为 `path_with_namespace`：
```
输入: https://nvwa.jiuqi.com.cn/gitlab/enterprise/gcreport/application/gcreport-carryover/gcreport-carryover-service/gcreport-carryover.git
提取: enterprise/gcreport/application/gcreport-carryover/gcreport-carryover-service/gcreport-carryover
```

### 方式二：通过 GitLab API 搜索

当本地没有代码时，使用 API 搜索：

1. **调用 GitLab API 搜索项目**：
   ```
   GET https://nvwa.jiuqi.com.cn/gitlab/api/v4/projects?search={模块名}
   ```
2. **从返回结果取 `path_with_namespace`**
3. **同一模块名可能返回多个项目**（如 gcreport-jra-service、gcreport-jra-web），需分别查询 SonarQube

### 凭证

使用 `~/.claude/jq-config.json` 中的 `gitlab.token`

### 示例

**方式一（本地）**：
```
输入: D:/JiuQi/code/enterprise-dev/service-copy/gcreport-carryover/.git/config
url: https://nvwa.jiuqi.com.cn/gitlab/enterprise/gcreport/application/gcreport-carryover/gcreport-carryover-service/gcreport-carryover.git
提取: enterprise/gcreport/application/gcreport-carryover/gcreport-carryover-service/gcreport-carryover
```

**方式二（API）**：
```
输入: gcreport-jra
调用: GET /projects?search=gcreport-jra
返回:
  - enterprise/gcreport/application/gcreport-jra/gcreport-jra-service/gcreport-jra
  - enterprise/gcreport/application/gcreport-jra/gcreport-jra-web/gcreport-jra
```

---

## 1. SonarKey 三步转换法

### 核心公式

```
SonarKey = GitLab路径.replace('/', '_') + '_' + 分支名
```

### 三步操作

1. **取路径** - 获取 GitLab 项目的 `path_with_namespace`（不含 `.git` 后缀）
2. **斜杠变下划线** - 把路径中所有 `/` 替换为 `_`
3. **加分支后缀** - 末尾加 `_` + 分支名（如 `_dev`、`_master`）

### 转换示例

**输入**: `enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service/gcreport-aidocaudit`
**分支**: `dev`

```
Step 1: 保留原路径
        enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service/gcreport-aidocaudit

Step 2: 斜杠变下划线
        enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_gcreport-aidocaudit

Step 3: 末尾加下划线分支名
        enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_gcreport-aidocaudit_dev
```

### 逆向验证

把 SonarKey 逆向还原为 GitLab 路径，验证转换是否正确：

```
SonarKey: enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_gcreport-aidocaudit_dev

Step 1: 删除分支后缀 _dev
        enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_gcreport-aidocaudit

Step 2: 下划线变斜杠
        enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service/gcreport-aidocaudit
        ✓ 还原成功，转换正确
```

### 常用分支后缀

| 分支 | SonarKey 后缀 |
|------|---------------|
| dev | `_dev` |
| master | `_master` |
| 其他 | `_{分支名}` |

### API 验证（可选）

推导出 SonarKey 后，可用 API 验证（返回 `total > 0` 即正确）：

```bash
curl -s "https://nvwa.jiuqi.com.cn/sonar/api/issues/search?components={SonarKey}&ps=1"
```

## 2. 查询方式

> **上下文管理**：用户说"这个项目"时，默认复用上一轮查询中出现的 Sonar Key。若上下文为空，先确认项目范围。

### 统计摘要（推荐）

**任务类型**：查询类
**输入**：`{Sonar Key}` 或 `{module名}`
**输出**：统计数字，不占上下文

当输入是模块名时：
1. 先调用 GitLab API `GET /projects?search={模块名}` 获取 `path_with_namespace`
2. 按三步转换法构造 SonarKey
3. 如有多个匹配项目，逐一查询 SonarQube 并汇总结果

> **数量统计**：若只需获取 BUG/VULNERABILITY 等类型的**计数**（不问详情），可改用 `GET /measures/component?component={SonarKey}&metricKeys=violations` 直接取指标，避免 issues/search 500 条上限。

**subagent 调用**：
```
subagent: 查询 gcreport-aidocaudit 的 Sonar 统计
```
> 支持两种输入：`{module名}`（自动构造 Sonar Key）或完整 `{Sonar Key}`

返回格式：
```
问题总数: 168
按 severity: BLOCKER=0, CRITICAL=0, MAJOR=76, MINOR=53, INFO=39
按 type: BUG=0, VULNERABILITY=0, CODE_SMELL=168
TOP5 规则:
  java:S1192 - 20个
  java:S1186 - 14个
  ...
```

### 问题详情

**任务类型**：查询类
**输入**：`{Sonar Key}` + 筛选参数（至少填一个）
**输出**：问题列表（最大500条/页，超限用 `page=2,3,...` 翻页）

| 查询目标 | subagent 调用方式 |
|---------|-----------------|
| 查指定规则 | `subagent: 查询 {SonarKey} 的 OPEN+java:S3776 问题` |
| 查严重级别 | `subagent: 查询 {SonarKey} 的 OPEN,MAJOR,CRITICAL,BLOCKER 问题` |
| 查问题类型 | `subagent: 查询 {SonarKey} 的 OPEN+BUG+VULNERABILITY 问题` |

> **注意**：`statuses=OPEN` 默认生效，需查已关闭问题时才需要额外指定。

### 规则修复建议

**任务类型**：修复类
**输入**：`{规则key}`（如 `java:S3776`）
**输出**：`descriptionSections` 字段，含 `how_to_fix`、`noncompliant code example`、`compliant solution`

**subagent 调用**：
```
subagent: 修复 {SonarKey} 的 java:S3776 问题
```

## 3. API 端点

| 操作 | 端点 |
|------|------|
| 问题搜索 | `GET /issues/search` |
| 规则详情 | `GET /rules/show` |
| 质量指标 | `GET /measures/component` |

### /issues/search 参数

> **多值分隔**：逗号 `,` 表示 OR 逻辑（如 `statuses=OPEN,CONFIRMED` 查 OPEN **或** CONFIRMED）。加号 `+` 在调用示例中用于分隔多个筛选维度。

| 参数 | 说明 | 示例 |
|------|------|------|
| components | Sonar Key | `enterprise_gcreport_..._dev` |
| statuses | 问题状态 | `OPEN`, `OPEN,CONFIRMED` |
| severities | 严重级别 | `MAJOR,CRITICAL,BLOCKER` |
| types | 问题类型 | `BUG`, `VULNERABILITY`, `CODE_SMELL` |
| rules | 规则 key | `java:S1118`, `java:S3776` |
| ps | 每页大小（最大500） | `ps=500` |
| page | 页码（从1开始） | `page=1`，超500条时用 `page=2` |

## 4. 问题状态

| Status | 含义 |
|--------|------|
| OPEN | 待处理 |
| CONFIRMED | 已确认 |
| CLOSED | 已修复 |
| RESOLVED | 已解决 |

## 5. 严重级别与类型

定义见 [Section 3 参数表](#3-api-端点) 的 `severities` 和 `types` 列。

## 6. Build 验证

**任务类型**：验证类

> **检查点**：执行 gradle build 前，确认已修复的问题类型和范围，避免全量构建浪费时间。

修复后必须执行 Build 验证：

**subagent 调用**：
```
subagent: 验证 {module} 的 Build
```

实际执行：
```bash
cd {module_dir} && gradle build -x test --no-daemon
```

**module_dir**：取 GitLab 路径最后一段
- `enterprise/gcreport/application/gcreport-aidocaudit/...` → `gcreport-aidocaudit`

**正确流程**：
```
修复一类问题 → subagent 验证 Build → 通过后继续下一类
```

## 7. 凭证配置

配置文件：`~/.claude/jq-config.json`

**模板文件**：`jq-config-template.json`（仅示例，不可直接使用）

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

**说明**：
- `gitlab.token` — GitLab Private Token，格式为 `glpat_xxx`
- `sonarqube.token` — SonarQube 用户令牌，格式为 `squ_xxx`
- `base_url` — API 地址，GitLab 固定为 `https://nvwa.jiuqi.com.cn/gitlab/api/v4`，SonarQube 固定为 `https://nvwa.jiuqi.com.cn/sonar/api`

首次使用需从 `jq-config-template.json` 复制配置到 `~/.claude/jq-config.json`，并填入真实 token。

## 8. 常用规则参考

| 规则 | 描述 | 级别 |
|------|------|------|
| java:S3776 | 认知复杂度超标 | MAJOR |
| java:S2259 | 空指针风险 | MAJOR |
| java:S1118 | 工具类应添加私有构造函数 | MAJOR |
| java:S1186 | 空方法需添加注释说明 | MINOR |
| java:S112 | 用具体异常替代通用异常 | MAJOR |
| java:S1149 | StringBuffer 应用 StringBuilder 替代 | MINOR |
| java:S1192 | 重复字面量 | INFO |
| java:S1854 | 无用赋值 | MINOR |

## 9. 错误处理

| 场景 | 原因 | 处理 |
|------|------|------|
| 返回空结果 | 项目无问题 / 筛选条件过严 | 先用 `statuses=OPEN` 不加过滤 |
| 401 Unauthorized | Token 过期 | 检查 `jq-config.json` |
| 404 Not Found | Sonar Key 不存在 | 后端用约定规则，前端用 GitLab 搜索 |