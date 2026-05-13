"""GitLab API 客户端"""
import requests
from typing import Optional


class GitLabClient:
    def __init__(self, base_url: str, token: str):
        """
        GitLab API 客户端
        :param base_url: GitLab API 地址，如 https://nvwa.jiuqi.com.cn/gitlab/api/v4
        :param token: GitLab token
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"PRIVATE-TOKEN": token})

    def _get(self, endpoint: str, **params) -> dict | list:
        """发送 GET 请求"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def search_projects(self, query: str, per_page: int = 20) -> list[dict]:
        """
        搜索项目
        :param query: 搜索关键词
        :param per_page: 每页数量
        """
        return self._get("projects", search=query, per_page=per_page)

    def get_project(self, project_path: str) -> dict:
        """
        获取项目详情
        :param project_path: 项目路径，如 enterprise/gcreport/application/gcreport-aidocaudit
        """
        import urllib.parse
        encoded_path = urllib.parse.quote(project_path, safe="")
        return self._get(f"projects/{encoded_path}")

    def get_branches(self, project_path: str) -> list[str]:
        """
        获取项目分支列表
        :param project_path: 项目路径
        """
        import urllib.parse
        encoded_path = urllib.parse.quote(project_path, safe="")
        branches = self._get(f"projects/{encoded_path}/repository/branches")
        return [b["name"] for b in branches]

    def project_exists(self, project_path: str) -> bool:
        """检查项目是否存在"""
        try:
            self.get_project(project_path)
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise
