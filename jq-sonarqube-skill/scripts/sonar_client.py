"""SonarQube API 客户端"""
import requests
from typing import Optional


class SonarClient:
    def __init__(self, base_url: str, token: str):
        """
        SonarQube API 客户端
        :param base_url: SonarQube API 地址，如 https://nvwa.jiuqi.com.cn/sonar/api
        :param token: SonarQube token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _get(self, endpoint: str, **params) -> dict:
        """发送 GET 请求"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search_issues(self, component: str, **kwargs) -> dict:
        """
        搜索问题
        :param component: 组件 key（即 SonarKey）
        :param statuses: 问题状态 (OPEN, CONFIRMED, CLOSED, RESOLVED)
        :param severities: 严重级别（BLOCKER, CRITICAL, MAJOR, MINOR, INFO）
        :param types: 问题类型（BUG, VULNERABILITY, CODE_SMELL）
        :param rules: 规则 key，如 java:S3776
        :param page: 页码
        :param ps: 每页数量
        """
        # 使用 components (复数) 代替 component
        kwargs["components"] = component
        # 使用 issueStatuses 代替 statuses
        if "statuses" in kwargs:
            kwargs["issueStatuses"] = kwargs.pop("statuses")
        # 使用 ps 代替 pageSize（SonarQube API 使用 ps 作为参数名）
        if "pageSize" in kwargs:
            kwargs["ps"] = kwargs.pop("pageSize")
        elif "ps" not in kwargs:
            kwargs["ps"] = 100
        # 添加 additionalFields 获取完整信息
        if "additionalFields" not in kwargs:
            kwargs["additionalFields"] = "_all"
        return self._get("issues/search", **kwargs)

    def get_issues_count(self, component: str, **kwargs) -> dict:
        """获取问题统计"""
        data = self.search_issues(component, **kwargs)
        counts = {"total": data.get("total", 0), "issues": data.get("issues", [])}

        severities = {"BLOCKER": 0, "CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "INFO": 0}
        types = {"BUG": 0, "VULNERABILITY": 0, "CODE_SMELL": 0}

        for issue in data.get("issues", []):
            severities[issue.get("severity", "INFO")] += 1
            types[issue.get("type", "CODE_SMELL")] += 1

        counts["by_severity"] = severities
        counts["by_type"] = types
        return counts

    def get_rule(self, rule_key: str) -> dict:
        """
        获取规则详情
        :param rule_key: 规则 key，如 java:S3776
        """
        return self._get("rules/show", key=rule_key)

    def get_measures(self, component: str, metric_keys: str) -> dict:
        """
        获取度量数据
        :param component: 组件 key
        :param metric_keys: 度量 key 列表，逗号分隔，如 bugs,vulnerabilities,code_smells
        """
        return self._get("measures/component", component=component, metricKeys=metric_keys)

    def get_component(self, component: str) -> dict:
        """获取组件信息"""
        return self._get("components/show", component=component)
