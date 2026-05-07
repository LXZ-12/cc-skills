# jq-sonarqube-skill

SonarQube 查询参考手册。Claude Code 技能，用于查询代码质量问题、统计分析和 Build 验证。

## 安装

### 方式一：使用 skill-install（推荐）

在 Claude Code 中运行：

```
/skill-install https://github.com/LXZ-12/cc-skills
```

### 方式二：手动安装

1. 下载本仓库
2. 将 `jq-sonarqube-skill/` 目录放入 `~/.claude/skills/`

## 配置

首次使用需配置凭证文件 `~/.claude/jq-config.json`：

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

- `gitlab.token` — GitLab Private Token（格式：`glpat_xxx`）
- `sonarqube.token` — SonarQube 用户令牌（格式：`squ_xxx`）

## 快速使用

### 查询统计摘要

```
subagent: 查询 {模块名} 的 Sonar 统计
```

### 查询问题详情

```
subagent: 查询 {SonarKey} 的 OPEN+MAJOR+CRITICAL+BLOCKER 问题
```

### 获取修复建议

```
subagent: 修复 {SonarKey} 的 java:S3776 问题
```

### Build 验证

```
subagent: 验证 {模块名} 的 Build
```

## SonarKey 构造

模块名 → GitLab 路径 → SonarKey 三步转换：

1. 获取 GitLab 项目路径（如 `enterprise/gcreport/application/gcreport-aidocaudit`）
2. 斜杠变下划线：`enterprise_gcreport_application_gcreport-aidocaudit`
3. 末尾加分支后缀：`enterprise_gcreport_application_gcreport-aidocaudit_dev`

## 详细文档

完整使用说明见 [SKILL.md](./SKILL.md)

