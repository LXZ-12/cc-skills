# jq-sonarqube-skill

SonarQube 查询参考手册。当用户提到 SonarQube、代码扫描、代码问题、Sonar 问题、代码质量时使用。

**核心能力**：问题统计、问题详情查询、规则修复建议、Build 验证。

---

## 安装

### 方式一：skill-install（推荐）

使用 Claude Code 的 skill-install 命令安装：

```
/skill-install https://github.com/gotta-tz/cc-skills/jq-sonarqube-skill
```

### 方式二：手动安装

将此 skill 目录放入 `~/.claude/skills/` 目录下。

---

## 配置

创建配置文件 `~/.claude/jq-config.json`：

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
- `gitlab.token`：GitLab → Settings → Access Tokens，格式 `glpat_xxx`
- `sonarqube.token`：SonarQube → My Account → Security，格式 `squ_xxx`

---

## 使用方式

必须通过 subagent 执行：

| 需求 | subagent 指令 |
|------|--------------|
| 快速看统计 | `subagent: 查询 {module} 的 Sonar 统计` |
| 查具体问题 | `subagent: 查询 {SonarKey} 的 OPEN+{severity}+{type} 问题` |
| 修复建议 | `subagent: 查询 java:S{编号} 规则的修复建议` |
| Build 验证 | `subagent: 验证 {module} 的 Build` |

---

## SonarKey 转换规则

```
SonarKey = GitLab路径.replace('/', '_') + '_' + 分支名
```

**示例**：`enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit_dev`
