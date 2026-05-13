"""查询命令入口 - CLI 工具"""
import sys
import json
import argparse
import time
import os
from pathlib import Path

from .log import setup_logging, log_query, get_logger
from .cache import QueryCache
from .sonar_client import SonarClient
from .gitlab_client import GitLabClient
from .sonarkey import gitlab_path_to_sonarkey, invalidate_sonarkey_cache


def load_config():
    """加载配置（搜索路径：当前目录 > skill目录 > 父目录）"""
    skill_dir = Path(__file__).parent.parent
    config_paths = [
        Path("jq-config.json"),
        skill_dir / "jq-config.json",
        skill_dir.parent / "jq-config.json",
        skill_dir.parent.parent / "jq-config.json",
    ]
    tried = []
    for p in config_paths:
        tried.append(str(p.resolve()))
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"jq-config.json not found. Looked in: {', '.join(tried)}\n"
        "Create one at any of the above paths with: "
        "{\"gitlab\": {\"token\": \"...\", \"base_url\": \"...\"}, "
        "\"sonarqube\": {\"token\": \"...\", \"base_url\": \"...\"}}"
    )


def get_clients():
    """获取 API 客户端"""
    config = load_config()
    sonar = SonarClient(
        base_url=config["sonarqube"]["base_url"],
        token=config["sonarqube"]["token"]
    )
    gitlab = GitLabClient(
        base_url=config["gitlab"]["base_url"],
        token=config["gitlab"]["token"]
    )
    return sonar, gitlab


def query_stats(sonarkey: str, use_cache: bool = True, statuses: str = None) -> dict:
    """查询统计摘要 - 使用 facets 获取各维度数量"""
    logger = get_logger()
    cache = QueryCache()

    start = time.time()
    cached = False

    filters = {"statuses": statuses} if statuses else None
    if use_cache:
        cached_entry = cache.get_data(sonarkey, "stats", filters)
        if cached_entry is not None:
            cached = True
            elapsed = time.time() - start
            data = cached_entry.get("data", {})
            total = data.get("total", 0)
            log_query(logger, "stats", sonarkey, cached=True, elapsed=elapsed, results=total)
            return data

    sonar, _ = get_clients()
    kwargs = {"ps": 1}
    if statuses:
        kwargs["statuses"] = statuses

    data = sonar.search_issues(component=sonarkey, facets="severities,types,impactSoftwareQualities", **kwargs)
    total = data.get("total", 0)

    severities = {"BLOCKER": 0, "CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "INFO": 0}
    types = {"BUG": 0, "VULNERABILITY": 0, "CODE_SMELL": 0}
    impacts = {}

    for facet in data.get("facets", []):
        if facet.get("property") == "severities":
            for val in facet.get("values", []):
                severities[val.get("val", "INFO")] = val.get("count", 0)
        elif facet.get("property") == "types":
            for val in facet.get("values", []):
                types[val.get("val", "CODE_SMELL")] = val.get("count", 0)
        elif facet.get("property") == "impactSoftwareQualities":
            for val in facet.get("values", []):
                impacts[val.get("val", "")] = val.get("count", 0)

    result = {
        "sonarkey": sonarkey,
        "total": total,
        "by_severity": severities,
        "by_type": types,
        "by_impact": impacts
    }

    if use_cache:
        cache.set_data(sonarkey, "stats", filters, result)

    elapsed = time.time() - start
    log_query(logger, "stats", sonarkey, cached=cached, elapsed=elapsed, results=total)
    return result


def query_issues(sonarkey: str, use_cache: bool = True, **filters) -> list:
    """查询问题详情"""
    logger = get_logger()
    cache = QueryCache()

    start = time.time()
    cached = False

    if use_cache:
        cached_entry = cache.get_data(sonarkey, "issues", filters)
        if cached_entry is not None:
            cached = True
            elapsed = time.time() - start
            items = cached_entry.get("items", [])
            log_query(logger, "issues", sonarkey, cached=True, elapsed=elapsed, results=len(items), filters=filters)
            return items

    sonar, _ = get_clients()
    data = sonar.search_issues(component=sonarkey, **filters)
    issues = data.get("issues", [])

    if use_cache:
        cache.set_data(sonarkey, "issues", filters, issues)

    elapsed = time.time() - start
    log_query(logger, "issues", sonarkey, cached=cached, elapsed=elapsed, results=len(issues), filters=filters)
    return issues


def query_rule(rule_key: str, use_cache: bool = True) -> dict:
    """查询规则详情"""
    logger = get_logger()
    cache = QueryCache()

    start = time.time()
    cached = False

    # 使用 __rules__ 作为虚拟 sonarkey，rule_key 存在 filters 中
    if use_cache:
        cached_entry = cache.get_data("__rules__", "rule", {"rule_key": rule_key})
        if cached_entry is not None:
            cached = True
            elapsed = time.time() - start
            log_query(logger, "rule", rule_key, cached=True, elapsed=elapsed)
            return cached_entry.get("data")

    sonar, _ = get_clients()
    data = sonar.get_rule(rule_key=rule_key)
    rule_info = data.get("rule", {})
    result = {
        "key": rule_info.get("key", rule_key),
        "name": rule_info.get("name", ""),
        "description": rule_info.get("description", "")
    }

    cache.set_data("__rules__", "rule", {"rule_key": rule_key}, result)

    elapsed = time.time() - start
    log_query(logger, "rule", rule_key, cached=cached, elapsed=elapsed)
    return result


def clear_cache(sonarkey: str = None):
    """清除查询缓存"""
    cache = QueryCache()
    cache.clear_data(sonarkey)
    print(f"Cache cleared for {sonarkey or 'all'}")


def clear_sonarkey_cache(gitlab_path: str = None):
    """清除 SonarKey 映射缓存"""
    invalidate_sonarkey_cache(gitlab_path)
    print(f"SonarKey cache cleared for {gitlab_path or 'all'}")


def clear_module_cache(module_name: str = None):
    """清除 Module 映射缓存"""
    cache = QueryCache()
    cache.clear_module_info(module_name)
    print(f"Module cache cleared for {module_name or 'all'}")


def warm_cache(queries_file: str):
    """预热缓存"""
    cache = QueryCache()
    queries = json.loads(Path(queries_file).read_text(encoding="utf-8"))
    sonar, _ = get_clients()

    def fetch_stats(sk):
        return sonar.get_issues_count(component=sk)

    def fetch_issues(sk, **filters):
        return sonar.search_issues(component=sk, **filters).get("issues", [])

    fetch_fn_map = {"stats": fetch_stats, "issues": fetch_issues}

    warmed = 0
    for q in queries:
        sk = q["sonarkey"]
        qt = q.get("query_type", "stats")
        filters = q.get("filters", {})
        if cache.get_data(sk, qt, filters or None) is None:
            fetch_fn = fetch_fn_map.get(qt)
            if fetch_fn:
                try:
                    data = fetch_fn(sk, **filters) if qt == "issues" else fetch_fn(sk)
                    cache.set_data(sk, qt, filters or None, data)
                    warmed += 1
                except Exception as e:
                    print(f"Failed to warm {sk}/{qt}: {e}")
    print(f"Warmed {warmed} cache entries")


def prefetch(sonarkey: str, query_types: list):
    """异步预取"""
    cache = QueryCache()
    sonar, _ = get_clients()

    def fetch_stats():
        return sonar.get_issues_count(component=sonarkey)

    def fetch_issues():
        return sonar.search_issues(component=sonarkey).get("issues", [])

    fetch_fn_map = {"stats": fetch_stats, "issues": fetch_issues}

    cache.prefetch_async(sonarkey, query_types, fetch_fn_map)
    print(f"Prefetch started for {sonarkey}: {query_types}")


def query_module(module_name: str, branch: str = "dev", use_cache: bool = True, limit: int = 50, **filters) -> dict:
    """
    统一查询模块的 Sonar 问题

    执行流程：
    1. 查询 GitLab 路径（优先从缓存，其次从本地 git，最后从 GitLab 搜索）
    2. 转换为 SonarKey
    3. 查询 SonarQube 问题

    :param module_name: 模块名称（支持模糊匹配）
    :param branch: 分支名，默认 dev
    :param use_cache: 是否使用缓存
    :param filters: 问题筛选条件（severities, types, statuses）
    :return: 包含 gitlab_path, sonarkey, stats, issues 的字典
    """
    import subprocess
    from pathlib import Path

    logger = get_logger()
    logger.info(f"=== 开始查询模块: {module_name} ===")

    cache = QueryCache()

    # ========== Step 1: 查询 GitLab 路径和 SonarKey（优先从缓存获取） ==========
    gitlab_path = None
    sonarkey = None
    if use_cache:
        cached_info = cache.get_module_info(module_name)
        if cached_info:
            gitlab_path = cached_info["gitlab_path"]
            sonarkey = cached_info["sonarkey"]
            logger.info(f"从缓存获取: GitLab={gitlab_path}, SonarKey={sonarkey}")

    # 1.1 如果缓存未命中，尝试从本地 git remote 获取
    if not gitlab_path:
        cwd = Path.cwd()
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # 从 URL 中提取路径 (e.g., https://nvwa.jiuqi.com.cn/gitlab/enterprise/gcreport/...)
                if "gitlab" in remote_url.lower():
                    # 提取路径部分
                    parts = remote_url.rsplit("/", 2)
                    if len(parts) >= 2:
                        gitlab_path = parts[-2] + "/" + parts[-1].replace(".git", "")
                        logger.info(f"从 git remote 获取路径: {gitlab_path}")
        except Exception as e:
            logger.warning(f"从 git remote 获取路径失败: {e}")

    # 1.2 如果本地获取失败，从 GitLab 搜索
    if not gitlab_path:
        _, gitlab = get_clients()
        logger.info(f"从 GitLab 搜索模块: {module_name}")
        projects = gitlab.search_projects(module_name, per_page=50)

        if projects:
            # 优先选择精确匹配的（路径最后一段正好是模块名）
            exact_matches = []
            for p in projects:
                path = p.get("path_with_namespace", "")
                # 获取路径的最后一段（模块名）
                last_segment = path.split("/")[-1].lower()
                if last_segment == module_name.lower():
                    exact_matches.append(path)

            # 从精确匹配中选择最长的路径（通常是最具体的）
            if exact_matches:
                gitlab_path = max(exact_matches, key=len)
            else:
                gitlab_path = projects[0].get("path_with_namespace")
            logger.info(f"从 GitLab 搜索到路径: {gitlab_path}")

            # 计算 SonarKey 并缓存完整信息
            if use_cache:
                sonarkey = gitlab_path_to_sonarkey(gitlab_path, branch, use_cache=False)
                cache.set_module_info(module_name, gitlab_path, sonarkey, branch)
                logger.info(f"已缓存 module '{module_name}' -> GitLab={gitlab_path}, SonarKey={sonarkey}")

    if not gitlab_path:
        raise ValueError(f"无法找到模块 {module_name} 的 GitLab 路径")
    if not sonarkey:
        sonarkey = gitlab_path_to_sonarkey(gitlab_path, branch, use_cache=use_cache)
    logger.info(f"SonarKey: {sonarkey}")

    # 验证 SonarKey 是否存在（通过 API 查询 total）
    sonar, _ = get_clients()
    try:
        test_data = sonar.search_issues(component=sonarkey, ps=1, statuses="OPEN,CONFIRMED")
        total = test_data.get("total", 0)
        if total == 0:
            logger.warning(f"SonarKey {sonarkey} 查询结果为 0，尝试搜索正确的 SonarKey...")
            # SonarKey 不存在，搜索所有可能的 SonarKey
            all_paths = [p.get("path_with_namespace") for p in projects] if projects else [gitlab_path]
            for try_path in all_paths:
                try_sonarkey = gitlab_path_to_sonarkey(try_path, branch, use_cache=False)
                try_data = sonar.search_issues(component=try_sonarkey, ps=1, statuses="OPEN,CONFIRMED")
                if try_data.get("total", 0) > 0:
                    sonarkey = try_sonarkey
                    gitlab_path = try_path
                    logger.info(f"找到有效 SonarKey: {sonarkey}")
                    break
    except Exception as e:
        logger.warning(f"验证 SonarKey 时出错: {e}")

    # SonarQube Dashboard URL（从 config 的 base_url 推导，去掉 /api 后缀）
    sonar_config = load_config()
    sonar_web_url = sonar_config["sonarqube"]["base_url"].rstrip("/").replace("/api", "")
    dashboard_url = f"{sonar_web_url}/project/issues?id={sonarkey}&issueStatuses=OPEN,CONFIRMED"

    print(f"\n┌─ 项目信息 ────────────────────────────────────────────────────────┐")
    print(f"│ GitLab: {gitlab_path:<64} │")
    print(f"│ SonarKey: {sonarkey:<64} │")
    print(f"└─────────────────────────────────────────────────────────────────┘")
    print(f"SonarQube Dashboard: {dashboard_url}")

    # ========== Step 3: 查询 SonarQube ==========
    # 默认过滤 OPEN + CONFIRMED 状态（与 SonarQube Web UI 一致）
    default_statuses = "OPEN,CONFIRMED"
    query_statuses = filters.pop("statuses", default_statuses) if filters else default_statuses

    # 查询统计（use_cache 由 query_module 参数决定）
    stats = query_stats(sonarkey, use_cache=use_cache, statuses=query_statuses)
    total = stats.get('total', 0)

    # 按严重级别统计
    severity_order = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
    by_severity = stats.get("by_severity", {})

    # 按类型统计
    by_type = stats.get("by_type", {})

    # 按影响统计
    by_impact = stats.get("by_impact", {})

    # 已处理问题列表（从所有缓存条目聚合）
    processed_keys = cache.get_all_processed_keys(sonarkey)

    # 打印统计表格
    print(f"\n{'=' * 80}")
    print(f"{module_name} SonarQube 问题汇总")
    print(f"{'=' * 80}")
    print(f"总问题数: {total}  |  已处理: {len(processed_keys)}  |  待处理: {total - len(processed_keys)}")
    print()

    print(f"{'─' * 80}")
    print(f"统计摘要:")
    print(f"{'─' * 80}")
    print(f"  总问题数 (OPEN+CONFIRMED): {total}")
    print(f"  严重级别:")
    for sev in severity_order:
        cnt = by_severity.get(sev, 0)
        if cnt > 0:
            print(f"    {sev}: {cnt}")
    print(f"  问题类型:")
    for t in ["BUG", "VULNERABILITY", "CODE_SMELL"]:
        cnt = by_type.get(t, 0)
        if cnt > 0:
            print(f"    {t}: {cnt}")
    if by_impact:
        print(f"  软件质量影响:")
        for quality, cnt in by_impact.items():
            print(f"    {quality}: {cnt}")

    # 查询问题详情（用于规则统计和展示）- 获取足够多的问题以覆盖所有规则
    if filters:
        issues = query_issues(sonarkey, use_cache=use_cache, pageSize=500, **filters)
    else:
        # 默认查询 OPEN/CONFIRMED 状态的问题，获取全部问题
        issues = query_issues(sonarkey, use_cache=use_cache, pageSize=500, statuses=query_statuses)

    # 从 issues 中提取规则统计（rule -> count, rule -> message）
    rule_stats = {}
    for issue in issues:
        rule = issue.get("rule", "")
        msg = issue.get("message", "")
        if rule:
            if rule not in rule_stats:
                rule_stats[rule] = {"count": 0, "message": msg}
            rule_stats[rule]["count"] += 1

    # 按规则统计表格
    if rule_stats:
        # 按数量排序
        sorted_rules = sorted(rule_stats.items(), key=lambda x: -x[1]["count"])

        print(f"\n{'=' * 100}")
        print(f"按规则分组:")
        print(f"{'-' * 100}")
        for rule, info in sorted_rules[:20]:
            rule_desc = info["message"][:70] if info["message"] else rule[:70]
            cnt = info["count"]
            print(f"  {rule:20} x{cnt:2}  {rule_desc}")
        if len(sorted_rules) > 20:
            print(f"  ... 还有 {len(sorted_rules) - 20} 个规则")

    # 问题详情表格 - 按待处理和已处理分组显示
    pending_issues = [i for i in issues if i.get('key', '') not in processed_keys]
    processed_issues = [i for i in issues if i.get('key', '') in processed_keys]

    # 待处理问题
    print(f"\n{'=' * 100}")
    print(f"待处理问题 ({len(pending_issues)}):")
    print(f"{'-' * 100}")
    for idx, issue in enumerate(pending_issues, 1):
        sev = issue.get('severity', 'UNKNOWN')
        msg = issue.get('message', '')
        rule = issue.get('rule', '')
        status = issue.get('status', '')
        component = issue.get('component', '').split(':')[-1] if ':' in issue.get('component', '') else issue.get('component', '')
        print(f"{idx:2}. {status:10} {sev:8} {rule:18} {msg[:50]}")
        print(f"    File: {component[:80]}")

    # 已处理问题
    print(f"\n{'=' * 100}")
    print(f"已处理问题 ({len(processed_issues)}):")
    print(f"{'-' * 100}")
    for idx, issue in enumerate(processed_issues, 1):
        sev = issue.get('severity', 'UNKNOWN')
        msg = issue.get('message', '')
        rule = issue.get('rule', '')
        status = issue.get('status', '')
        component = issue.get('component', '').split(':')[-1] if ':' in issue.get('component', '') else issue.get('component', '')
        print(f"{idx:2}. {status:10} {sev:8} {rule:18} {msg[:50]}")
        print(f"    File: {component[:80]}")

    return {
        "gitlab_path": gitlab_path,
        "sonarkey": sonarkey,
        "stats": stats,
        "issues": issues,
        "processed_keys": list(processed_keys)
    }


def cleanup_cache():
    """清理过期缓存"""
    cache = QueryCache()
    count = cache.cleanup_expired()
    print(f"Cleaned up {count} expired cache entries")


def main():
    # Windows 控制台 UTF-8 编码修复
    if sys.platform == "win32":
        import io
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    setup_logging()

    parser = argparse.ArgumentParser(description="SonarQube 查询工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    stats_parser = subparsers.add_parser("stats", help="查询统计摘要")
    stats_parser.add_argument("sonarkey", help="SonarKey")
    stats_parser.add_argument("--no-cache", action="store_true", help="跳过缓存")

    issues_parser = subparsers.add_parser("issues", help="查询问题详情")
    issues_parser.add_argument("sonarkey", help="SonarKey")
    issues_parser.add_argument("--severity", help="严重级别")
    issues_parser.add_argument("--type", help="问题类型")
    issues_parser.add_argument("--status", help="问题状态")
    issues_parser.add_argument("--rule", help="规则编码，如 java:S3776")
    issues_parser.add_argument("--no-cache", action="store_true", help="跳过缓存")

    rule_parser = subparsers.add_parser("rule", help="查询规则详情")
    rule_parser.add_argument("rule_key", help="规则 key，如 java:S3776")
    rule_parser.add_argument("--no-cache", action="store_true", help="跳过缓存")

    clear_parser = subparsers.add_parser("clear", help="清除查询缓存")
    clear_parser.add_argument("sonarkey", nargs="?", help="指定 SonarKey，为空则清除全部")
    clear_parser.add_argument("--all", action="store_true", help="清除全部")

    sonarkey_parser = subparsers.add_parser("clear-sonarkey", help="清除 SonarKey 映射缓存")
    sonarkey_parser.add_argument("gitlab_path", nargs="?", help="指定 GitLab 路径，为空则清除全部")

    module_parser = subparsers.add_parser("clear-module", help="清除 Module 映射缓存")
    module_parser.add_argument("module_name", nargs="?", help="指定模块名，为空则清除全部")

    warm_parser = subparsers.add_parser("warm", help="预热缓存")
    warm_parser.add_argument("--file", required=True, help="预热查询 JSON 文件")

    prefetch_parser = subparsers.add_parser("prefetch", help="异步预取")
    prefetch_parser.add_argument("sonarkey", help="SonarKey")
    prefetch_parser.add_argument("--types", default="stats,issues", help="查询类型，逗号分隔")

    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期缓存")

    module_parser = subparsers.add_parser("module", help="统一查询模块 Sonar 问题")
    module_parser.add_argument("module_name", help="模块名称")
    module_parser.add_argument("--branch", default="dev", help="分支名，默认 dev")
    module_parser.add_argument("--no-cache", action="store_true", help="跳过缓存")
    module_parser.add_argument("--severity", help="严重级别：BLOCKER, CRITICAL, MAJOR, MINOR, INFO")
    module_parser.add_argument("--type", help="问题类型：BUG, VULNERABILITY, CODE_SMELL")
    module_parser.add_argument("--status", help="问题状态：OPEN, CONFIRMED, CLOSED, RESOLVED")
    module_parser.add_argument("--limit", type=int, default=50, help="显示问题数量，默认 50")

    args = parser.parse_args()

    if args.command == "stats":
        result = query_stats(args.sonarkey, use_cache=not args.no_cache)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "issues":
        filters = {}
        if args.severity:
            filters["severities"] = args.severity
        if args.type:
            filters["types"] = args.type
        if args.status:
            filters["statuses"] = args.status
        result = query_issues(args.sonarkey, use_cache=not args.no_cache, **filters)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "rule":
        result = query_rule(args.rule_key, use_cache=not args.no_cache)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "clear":
        clear_cache(args.sonarkey if args.sonarkey else None)

    elif args.command == "clear-sonarkey":
        clear_sonarkey_cache(args.gitlab_path if args.gitlab_path else None)

    elif args.command == "clear-module":
        clear_module_cache(args.module_name if args.module_name else None)

    elif args.command == "warm":
        warm_cache(args.file)

    elif args.command == "prefetch":
        types = [t.strip() for t in args.types.split(",")]
        prefetch(args.sonarkey, types)

    elif args.command == "cleanup":
        cleanup_cache()

    elif args.command == "module":
        filters = {}
        if args.severity:
            filters["severities"] = args.severity.upper()
        if args.type:
            filters["types"] = args.type.upper()
        if args.status:
            filters["statuses"] = args.status.upper()
        query_module(args.module_name, branch=args.branch, use_cache=not args.no_cache, limit=args.limit, **filters)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
