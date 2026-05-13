# jq-sonarqube-skill

SonarQube 查询参考手册。当用户提到 SonarQube、代码扫描、代码问题、Sonar 问题、代码质量时使用。

**核心能力**：问题统计、问题详情查询、规则修复建议。

---

## 配置

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

## 快速使用

```bash
# 统计摘要
python -m scripts.queries stats <sonarkey>

# 问题详情
python -m scripts.queries issues <sonarkey> --severity MAJOR

# 规则详情
python -m scripts.queries rule java:S3776

# 缓存控制
python -m scripts.queries clear <sonarkey>    # 清除缓存
python -m scripts.queries cleanup             # 清理过期缓存
```
