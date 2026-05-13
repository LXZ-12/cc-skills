"""SonarKey 转换工具 - GitLab 路径 <-> SonarKey"""
import re
from typing import Optional
from .cache import QueryCache


_cache = QueryCache()


def gitlab_path_to_sonarkey(path: str, branch: str = "dev", use_cache: bool = True) -> str:
    """
    GitLab 路径 -> SonarKey

    转换规则：
    - 将路径中的 / 替换为 _
    - 添加 _<branch> 后缀

    示例：
        enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service
        -> enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_dev

    :param path: GitLab 项目路径
    :param branch: 分支名，默认 dev
    :param use_cache: 是否使用缓存
    """
    if use_cache:
        cached = _cache.get_sonarkey(path)
        if cached:
            return cached

    sonarkey = _path_to_sonarkey(path, branch)

    if use_cache:
        _cache.set_sonarkey(path, sonarkey)

    return sonarkey


def _path_to_sonarkey(path: str, branch: str = "dev") -> str:
    """内部转换函数"""
    return f"{path.replace('/', '_')}_{branch}"


def sonarkey_to_gitlab_path(sonarkey: str) -> str:
    """
    SonarKey -> GitLab 路径（逆向验证）

    示例：
        enterprise_gcreport_application_gcreport-aidocaudit_gcreport-aidocaudit-service_dev
        -> enterprise/gcreport/application/gcreport-aidocaudit/gcreport-aidocaudit-service

    注意：无法确定原始分支，返回不带后缀的路径
    """
    if sonarkey.endswith("_dev"):
        sonarkey = sonarkey[:-4]
    elif sonarkey.endswith("_master"):
        sonarkey = sonarkey[:-7]
    elif sonarkey.endswith("_main"):
        sonarkey = sonarkey[:-5]

    branch_suffix_match = re.search(r"_(dev|master|main|test|feature_.*)$", sonarkey)
    if branch_suffix_match:
        sonarkey = sonarkey[:branch_suffix_match.start()]

    return sonarkey.replace("_", "/")


def invalidate_sonarkey_cache(path: str = None):
    """使 SonarKey 映射缓存失效"""
    _cache.clear_sonarkey(path)


def get_cache() -> QueryCache:
    """获取缓存实例"""
    return _cache
