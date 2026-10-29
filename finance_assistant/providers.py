import re
import math
from collections import Counter
from urllib.parse import urlparse
import hashlib
import json

import httpx

from .config import Settings
from .documents import SUPPORTED, extract

KNOWLEDGE_EXTENSIONS = SUPPORTED | {".jsonl"}


def knowledge_files(directory):
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in KNOWLEDGE_EXTENSIONS
                  and not any(part.startswith(".") for part in p.relative_to(directory).parts))


class ConfigurationError(ValueError):
    pass


class ProviderError(RuntimeError):
    pass


def validate_endpoint(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError("API 地址格式不正确，请填写不含凭据的 HTTP(S) 地址。")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ConfigurationError("远程 API 地址需使用 HTTPS；本机服务可使用 HTTP。")


class ChatModel:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, messages, model_config):
        s = self.settings
        if not s.api_key:
            raise ConfigurationError("尚未配置模型 API key。请在侧栏填写，或在项目 .env 中配置 MODEL_API_KEY。")
        validate_endpoint(s.base_url)
        params = model_config.get("completion_params", {})
        payload = {"model": s.model or model_config["name"], "messages": messages,
                   "temperature": params.get("temperature", 0.7), "stream": False}
        if "thinking" in params and urlparse(s.base_url).hostname == "api.deepseek.com":
            payload["thinking"] = {"type": "enabled" if params["thinking"] else "disabled"}
        try:
            response = httpx.post(s.base_url + "/chat/completions", json=payload,
                                  headers={"Authorization": f"Bearer {s.api_key}"}, timeout=s.timeout)
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ProviderError("模型没有返回正文，请检查模型与非思考模式配置。")
            return text.strip()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = {401: "密钥无效", 402: "余额不足", 403: "没有调用权限", 404: "接口或模型不存在", 429: "调用频率或额度受限"}.get(code, "服务端拒绝请求")
            raise ProviderError(f"模型请求失败：HTTP {code}（{hint}）。检查侧栏或 .env 配置。") from None
        except httpx.RequestError:
            raise ProviderError("模型连接失败或超时，请检查网络和 API 地址。") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("模型响应格式不兼容，预期 Chat Completions 格式。") from None


def tokens(text):
    result = re.findall(r"[a-z0-9]+", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) == 1:
            result.append(run)
    return result


class LocalKnowledge:
    """Independent document collection with BM25 retrieval and provenance."""
    def __init__(self, directory):
        self.directory = directory
        self.chunks = None
        self.documents = []
        self.record_count = 0

    def _structured_records(self, path, raw, chunks):
        try:
            records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        except (ValueError, UnicodeDecodeError):
            raise ConfigurationError(f"{path.name} 不是有效的 UTF-8 JSONL 知识库。") from None
        for record in records:
            if not isinstance(record, dict) or not all(record.get(key) for key in ("id", "text", "source", "location")):
                raise ConfigurationError(f"{path.name} 中的知识记录缺少 ID、正文或来源位置。")
            text = record["text"]
            if not isinstance(text, str):
                raise ConfigurationError(f"{path.name} 中的知识正文必须为字符串。")
            for start in range(0, len(text), 850):
                content = text[start:start + 1000]
                chunks.append({"id": f"{record['id']}:{start}", "record_id": record["id"],
                               "source": record["source"], "location": record["location"],
                               "title": record.get("title", ""), "sheet": record.get("sheet", ""),
                               "source_url": record.get("source_url", ""),
                               "evidence_type": record.get("evidence_type", ""),
                               "verification_status": record.get("verification_status", ""),
                               "source_sha256": record.get("source_sha256", ""),
                               "content": content,
                               "terms": Counter(tokens(record.get("title", "") + "\n" + content))})
        self.record_count += len(records)
        self.documents.append({"source": path.relative_to(self.directory).as_posix(),
                               "sha256": hashlib.sha256(raw).hexdigest(), "records": len(records),
                               "characters": sum(len(r["text"]) for r in records)})

    def _load(self):
        chunks = []
        if self.directory.exists():
            for path in knowledge_files(self.directory):
                raw = path.read_bytes()
                if path.suffix.lower() == ".jsonl":
                    self._structured_records(path, raw, chunks)
                    continue
                text = extract(path.name, raw)
                digest = hashlib.sha256(raw).hexdigest()
                self.documents.append({"source": path.relative_to(self.directory).as_posix(),
                                       "sha256": digest, "characters": len(text)})
                for start in range(0, len(text), 850):
                    content = text[start:start + 1000]
                    chunks.append({"id": f"{path.relative_to(self.directory).as_posix()}:{start}",
                                   "source": path.relative_to(self.directory).as_posix(),
                                   "location": f"字符 {start + 1}–{start + len(content)}",
                                   "content": content, "source_sha256": digest, "terms": Counter(tokens(content))})
        self.chunks = chunks

    def status(self):
        if self.chunks is None:
            self._load()
        return {"ready": bool(self.chunks), "file_count": len(self.documents),
                "chunk_count": len(self.chunks), "record_count": self.record_count, "documents": self.documents}

    def retrieve(self, query, top_k=4):
        if self.chunks is None:
            self._load()
        if not self.chunks:
            return [], ["自有知识库为空：请先导入法规或制度资料，本次无法据此形成完整合规结论。"]
        terms = set(tokens(query))
        n = len(self.chunks)
        average = sum(sum(c["terms"].values()) for c in self.chunks) / n or 1
        df = {t: sum(t in c["terms"] for c in self.chunks) for t in terms}
        scored = []
        for c in self.chunks:
            length = sum(c["terms"].values())
            score = 0.0
            for term in terms:
                freq = c["terms"][term]
                if freq:
                    idf = math.log(1 + (n - df[term] + .5) / (df[term] + .5))
                    score += idf * freq * 2.5 / (freq + 1.5 * (.25 + .75 * length / average))
            if score > 0:
                scored.append({k: v for k, v in c.items() if k != "terms"} | {"score": round(score, 5)})
        scored.sort(key=lambda c: (-c["score"], c["id"]))
        warnings = []
        if not scored:
            warnings.append("未检索到相关依据，请补充适用法规或调整问题。")
        return scored[:top_k], warnings


def knowledge_provider(settings):
    if settings.knowledge_backend == "local":
        return LocalKnowledge(settings.knowledge_dir)
    raise ConfigurationError("当前版本仅使用项目自有知识库，请将 KNOWLEDGE_BACKEND 设为 local。")
