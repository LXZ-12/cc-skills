"""查询缓存模块 - 一 sonarkey 一文件 + 已处理问题标记"""
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable


def _filters_key(filters: dict = None) -> str:
    """将 filters 字典转换为字符串 key"""
    if not filters:
        return "_default"
    return "&".join(f"{k}={v}" for k, v in sorted(filters.items()))


class QueryCache:
    def __init__(self, cache_dir: str = None, ttl_hours: int = 1, mapping_ttl_hours: int = 168):
        """
        查询缓存 - 一 sonarkey 一文件存储
        - 缓存路径: ~/.cache/sonar_queries/sonar/<sonarkey>.json
        - TTL: 默认 1 小时
        - stale 阈值: 10 分钟（过期前 10 分钟开始后台刷新）
        - 模块映射 TTL: 7 天（独立文件）
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "sonar_queries"
        self.cache_dir = Path(cache_dir)
        self.sonar_dir = self.cache_dir / "sonar"
        self.sonar_dir.mkdir(parents=True, exist_ok=True)
        self.module_map_file = self.sonar_dir / "module_map.json"
        self.ttl = timedelta(hours=ttl_hours)
        self.stale_threshold = timedelta(minutes=10)
        self.mapping_ttl = timedelta(hours=mapping_ttl_hours)
        self._module_cache = self._load_module_map()
        self._lock = threading.Lock()

    def _sonarkey_file(self, sonarkey: str) -> Path:
        return self.sonar_dir / f"{sonarkey}.json"

    def _load_sonarkey_data(self, sonarkey: str) -> dict | None:
        """加载 sonarkey 数据文件"""
        f = self._sonarkey_file(sonarkey)
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_sonarkey_data(self, sonarkey: str, data: dict):
        """保存 sonarkey 数据文件"""
        f = self._sonarkey_file(sonarkey)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_module_map(self) -> dict:
        """加载模块映射缓存"""
        old_sonarkey_file = self.sonar_dir / "sonarkey_map.json"
        if old_sonarkey_file.exists():
            try:
                old_sonarkey_file.unlink()
            except OSError:
                pass

        if self.module_map_file.exists():
            try:
                return json.loads(self.module_map_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_module_map(self):
        """保存模块映射缓存"""
        self.module_map_file.write_text(json.dumps(self._module_cache, ensure_ascii=False, indent=2), encoding="utf-8")

    # ==================== 查询结果缓存 API ====================

    def get_data(self, sonarkey: str, query_type: str, filters: dict = None) -> dict | None:
        """
        获取查询结果，支持 TTL 过期检查
        返回: {"items": [...], "processed_keys": [...], "cached_at": "..."} 或 None
        """
        data = self._load_sonarkey_data(sonarkey)
        if data is None:
            return None

        fkey = _filters_key(filters)
        section = data.get(query_type, {})
        entry = section.get(fkey)

        if entry is None:
            return None

        # 检查 TTL
        cached_at = entry.get("cached_at")
        if cached_at:
            try:
                created = datetime.fromisoformat(cached_at)
                if datetime.now() - created > self.ttl:
                    return None
            except (ValueError, OSError):
                return None

        return entry

    def set_data(self, sonarkey: str, query_type: str, filters: dict, value: dict):
        """写入查询结果（保留已处理的 processed_keys）"""
        fkey = _filters_key(filters)
        data = self._load_sonarkey_data(sonarkey) or {"sonarkey": sonarkey}

        # 保留已处理的 keys（issues 类型）
        section = data.get(query_type, {})
        existing_entry = section.get(fkey, {})
        processed_keys = existing_entry.get("processed_keys", [])

        if query_type == "issues":
            entry = {
                "items": value if isinstance(value, list) else [],
                "processed_keys": processed_keys,
                "cached_at": datetime.now().isoformat()
            }
        else:
            entry = {
                "data": value,
                "cached_at": datetime.now().isoformat()
            }

        section[fkey] = entry
        data[query_type] = section
        data["cached_at"] = datetime.now().isoformat()
        self._save_sonarkey_data(sonarkey, data)

    def get_processed_keys(self, sonarkey: str, filters: dict = None) -> set[str]:
        """获取已处理的 issue keys"""
        entry = self.get_data(sonarkey, "issues", filters)
        if entry is None:
            return set()
        return set(entry.get("processed_keys", []))

    def get_all_processed_keys(self, sonarkey: str) -> set[str]:
        """获取该 sonarkey 下所有已处理的 issue keys（从所有 filter 条目聚合）"""
        data = self._load_sonarkey_data(sonarkey)
        if data is None:
            return set()
        all_keys = set()
        issues_section = data.get("issues", {})
        for entry in issues_section.values():
            all_keys.update(entry.get("processed_keys", []))
        return all_keys

    def mark_processed(self, sonarkey: str, issue_keys: list[str], filters: dict = None):
        """标记 issues 为已处理"""
        fkey = _filters_key(filters)
        data = self._load_sonarkey_data(sonarkey)
        if data is None:
            return

        section = data.get("issues", {})
        entry = section.get(fkey, {"items": [], "processed_keys": []})

        current = set(entry.get("processed_keys", []))
        current.update(issue_keys)
        entry["processed_keys"] = list(current)
        section[fkey] = entry
        data["issues"] = section
        self._save_sonarkey_data(sonarkey, data)

    def unmark_processed(self, sonarkey: str, issue_keys: list[str], filters: dict = None):
        """取消已处理标记"""
        fkey = _filters_key(filters)
        data = self._load_sonarkey_data(sonarkey)
        if data is None:
            return

        section = data.get("issues", {})
        entry = section.get(fkey, {"items": [], "processed_keys": []})

        current = set(entry.get("processed_keys", []))
        current.difference_update(issue_keys)
        entry["processed_keys"] = list(current)
        section[fkey] = entry
        data["issues"] = section
        self._save_sonarkey_data(sonarkey, data)

    def clear_data(self, sonarkey: str = None):
        """清除查询结果缓存"""
        if sonarkey is None:
            for f in self.sonar_dir.glob("*.json"):
                if f.name != "module_map.json":
                    f.unlink()
            return

        f = self._sonarkey_file(sonarkey)
        if f.exists():
            f.unlink()

    # ==================== Stale-While-Revalidate ====================

    def get_with_revalidate(self, sonarkey: str, query_type: str, filters: dict, fetch_fn: Callable) -> dict | None:
        """
        Stale-While-Revalidate 模式
        - 缓存存在但已 stale 时：立即返回旧缓存，同时后台异步刷新
        - 缓存不存在时：同步获取新数据
        """
        entry = self.get_data(sonarkey, query_type, filters)
        if entry is not None:
            if self._is_stale(sonarkey, query_type, filters):
                threading.Thread(target=self._revalidate, args=(sonarkey, query_type, filters, fetch_fn), daemon=True).start()
            return entry
        return fetch_fn()

    def _is_stale(self, sonarkey: str, query_type: str, filters: dict = None) -> bool:
        """检查缓存是否处于 stale 状态（即将过期前 stale_threshold）"""
        entry = self.get_data(sonarkey, query_type, filters)
        if entry is None:
            return True
        cached_at = entry.get("cached_at")
        if not cached_at:
            return True
        try:
            created = datetime.fromisoformat(cached_at)
            return datetime.now() - created > (self.ttl - self.stale_threshold)
        except (ValueError, OSError):
            return True

    def _revalidate(self, sonarkey: str, query_type: str, filters: dict, fetch_fn: Callable):
        """后台刷新缓存"""
        try:
            data = fetch_fn()
            self.set_data(sonarkey, query_type, filters, data)
        except Exception:
            pass

    # ==================== 预热与预取 ====================

    def warm(self, queries: list[dict]):
        """
        预热缓存 - 主动填充常用查询
        queries: [{"sonarkey": "...", "query_type": "stats", "filters": {}, "fetch_fn": callable}, ...]
        """
        for q in queries:
            sk = q["sonarkey"]
            qt = q.get("query_type", "stats")
            filters = q.get("filters", {})
            if self.get_data(sk, qt, filters) is None and q.get("fetch_fn"):
                try:
                    data = q["fetch_fn"]()
                    self.set_data(sk, qt, filters, data)
                except Exception:
                    pass

    def prefetch_async(self, sonarkey: str, query_types: list[str], fetch_fn_map: dict):
        """异步预取 - 后台线程预取指定 sonarkey 的所有查询类型"""
        def _prefetch():
            for qt in query_types:
                if self.get_data(sonarkey, qt) is None:
                    fetch_fn = fetch_fn_map.get(qt)
                    if fetch_fn:
                        try:
                            data = fetch_fn()
                            self.set_data(sonarkey, qt, None, data)
                        except Exception:
                            pass

        threading.Thread(target=_prefetch, daemon=True).start()

    # ==================== 清理过期 ====================

    def cleanup_expired(self) -> int:
        """清理过期缓存文件，返回清理数量"""
        count = 0
        for f in self.sonar_dir.glob("*.json"):
            if f.name == "module_map.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                expired = True
                # 检查是否所有数据都过期
                for qt in ["stats", "issues", "rules"]:
                    section = data.get(qt, {})
                    for entry in section.values():
                        cached_at = entry.get("cached_at")
                        if cached_at:
                            try:
                                created = datetime.fromisoformat(cached_at)
                                if datetime.now() - created <= self.ttl:
                                    expired = False
                                    break
                            except (ValueError, OSError):
                                pass
                    if not expired:
                        break
                if expired:
                    f.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError):
                f.unlink()
                count += 1
        return count

    # ==================== 模块映射缓存（独立文件，7d TTL） ====================

    def get_module_info(self, module_name: str) -> dict | None:
        """获取模块的完整信息，返回: {gitlab_path, sonarkey, branch} 或 None"""
        entry = self._module_cache.get(module_name)
        if entry is None:
            return None

        cached_at = datetime.fromisoformat(entry["cached_at"])
        if datetime.now() - cached_at > self.mapping_ttl:
            del self._module_cache[module_name]
            self._save_module_map()
            return None

        return {
            "gitlab_path": entry["gitlab_path"],
            "sonarkey": entry["sonarkey"],
            "branch": entry.get("branch", "dev")
        }

    def set_module_info(self, module_name: str, gitlab_path: str, sonarkey: str, branch: str = "dev"):
        """缓存模块完整信息"""
        self._module_cache[module_name] = {
            "gitlab_path": gitlab_path,
            "sonarkey": sonarkey,
            "branch": branch,
            "cached_at": datetime.now().isoformat()
        }
        self._save_module_map()

    def clear_module_info(self, module_name: str = None):
        """清除模块映射缓存"""
        if module_name is None:
            self._module_cache.clear()
        else:
            self._module_cache.pop(module_name, None)
        self._save_module_map()

    # ==================== 兼容性别名 ====================

    def get_sonarkey(self, gitlab_path: str) -> str | None:
        """通过 gitlab_path 查找 sonarkey（兼容旧代码）"""
        for entry in self._module_cache.values():
            if entry.get("gitlab_path") == gitlab_path:
                return entry.get("sonarkey")
        return None

    def set_sonarkey(self, gitlab_path: str, sonarkey: str):
        """不推荐使用，请使用 set_module_info"""
        pass

    def clear_sonarkey(self, gitlab_path: str = None):
        """清除 sonarkey 映射（兼容旧代码）"""
        if gitlab_path is None:
            self._module_cache.clear()
        else:
            to_remove = [k for k, v in self._module_cache.items() if v.get("gitlab_path") == gitlab_path]
            for k in to_remove:
                self._module_cache.pop(k)
        self._save_module_map()
