import re
import math
from collections import Counter
from urllib.parse import urlparse
from uuid import UUID

import httpx

from .config import Settings
from .documents import SUPPORTED, extract


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
    """Local BM25 fallback, explicitly different from Dify vector retrieval."""
    def __init__(self, directory):
        self.directory = directory
        self.chunks = None

    def _load(self):
        chunks = []
        if self.directory.exists():
            for path in sorted(self.directory.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED or path.name.startswith("."):
                    continue
                text = extract(path.name, path.read_bytes())
                for start in range(0, len(text), 850):
                    content = text[start:start + 1000]
                    chunks.append({"id": f"{path.relative_to(self.directory).as_posix()}:{start}",
                                   "source": path.relative_to(self.directory).as_posix(),
                                   "location": f"字符 {start + 1}–{start + len(content)}",
                                   "content": content, "terms": Counter(tokens(content))})
        self.chunks = chunks

    def retrieve(self, query, top_k=4):
        if self.chunks is None:
            self._load()
        if not self.chunks:
            return [], ["本地知识库为空：尚未接入原法规资料，本次无法据此形成完整合规结论。"]
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
        warnings = ["本地采用 BM25 文本检索，与 Dify 原向量检索结果不保证一致。"]
        if not scored:
            warnings.append("未检索到相关依据，请补充适用法规或调整问题。")
        return scored[:top_k], warnings


class DifyKnowledge:
    def __init__(self, settings):
        self.settings = settings

    def retrieve(self, query, top_k=4):
        s = self.settings
        if not s.dify_api_key or not s.dify_dataset_id:
            raise ConfigurationError("请配置 DIFY_DATASET_API_KEY 和 DIFY_DATASET_ID（知识库真实 UUID，不能使用 DSL 中的加密标识）。")
        try:
            UUID(s.dify_dataset_id)
        except ValueError:
            raise ConfigurationError("DIFY_DATASET_ID 必须是知识库真实 UUID，请从 Dify 知识库页面或 API 获取。") from None
        validate_endpoint(s.dify_base_url)
        # DSL omits dataset-level embedding/search settings. Leave them at the server defaults.
        payload = {"query": query[:250]}
        if s.dify_search_method:
            payload["retrieval_model"] = {"search_method": s.dify_search_method,
                                          "top_k": top_k, "reranking_enable": False,
                                          "score_threshold_enabled": False}
        warnings = ["Dify 检索使用知识库端配置，返回片段最多保留 4 条；底层索引配置不在 DSL 中。"]
        if len(query) > 250:
            warnings.append("Dify 检索接口限制 250 字，本次检索使用查询前 250 字；模型仍接收完整审查材料。")
        try:
            r = httpx.post(f"{s.dify_base_url}/datasets/{s.dify_dataset_id}/retrieve", json=payload,
                           headers={"Authorization": f"Bearer {s.dify_api_key}"}, timeout=s.timeout)
            r.raise_for_status()
            result = []
            for record in r.json()["records"][:top_k]:
                seg = record["segment"]
                if seg.get("enabled") is False:
                    continue
                result.append({"id": seg["id"], "source": seg.get("document", {}).get("name", "Dify 知识库"),
                               "location": f"片段 {seg.get('position', '')}", "content": seg["content"],
                               "score": record.get("score", 0)})
            if not result:
                warnings.append("Dify 知识库没有返回相关依据。")
            return result, warnings
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Dify 知识库请求失败：HTTP {exc.response.status_code}。请检查知识库密钥、UUID 和 API 权限。") from None
        except httpx.RequestError:
            raise ProviderError("Dify 知识库连接失败或超时。") from None
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Dify 知识库响应格式不符合预期。") from None


def knowledge_provider(settings):
    if settings.knowledge_backend == "dify":
        return DifyKnowledge(settings)
    if settings.knowledge_backend == "local":
        return LocalKnowledge(settings.knowledge_dir)
    raise ConfigurationError("KNOWLEDGE_BACKEND 只能为 local 或 dify。")
