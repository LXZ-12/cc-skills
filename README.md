# CC Skills

久其内部 Claude Code Skills 集合。

## 目录结构

\`\`\`
cc-skills/
└── jq-sonarqube-skill/     # SonarQube 查询技能
    ├── SKILL.md             # 技能主文档
    ├── test-prompts.json    # 测试用例
    └── jq-config-template.json  # 配置文件模板
\`\`\`

## 技能列表

### jq-sonarqube-skill

SonarQube 查询参考手册。

**触发场景**：用户提到 SonarQube、代码扫描、代码问题、Sonar 问题、代码质量

**核心能力**：
- 问题统计
- 问题详情查询
- 规则修复建议
- Build 验证

## 安装

使用 Claude Code 安装：

```
/skill-install https://github.com/LXZ-12/cc-skills
```

## 配置文件

安装后需配置 \`~/.claude/jq-config.json\`，模板见各技能目录下的 \`jq-config-template.json\`。

