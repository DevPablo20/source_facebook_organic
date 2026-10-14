"""Cliente da Graph API: derivação de token, paginação, batch e backoff por header de uso."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

GRAPH_HOST = "https://graph.facebook.com"

# Códigos que a Meta usa para limite de uso; qualquer outro erro sobe.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80001, 80002, 80003, 80004}
INVALID_METRIC_CODE = 100
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
OVERSIZED_HINT = "reduce the amount of data"
MIN_PAGE_SIZE = 5

MAX_RETRIES = 8
BATCH_SIZE = 50


def redact(text: str) -> str:
    """Nenhum token sai em log, mensagem de erro ou traceback."""
    return re.sub(r"(access_token=)[^&\s]+", r"\1<redacted>", str(text))


class GraphAPIError(Exception):
    def __init__(self, error: Mapping[str, Any], context: str = ""):
        self.code = error.get("code")
        self.subcode = error.get("error_subcode")
        self.message = redact(error.get("message", ""))
        super().__init__(redact(f"{context}{self.message} (code={self.code} subcode={self.subcode})"))


class GraphAPI:
    """Toda chamada à Graph API passa por aqui. Nenhum token sai em registro."""

    def __init__(self, access_token: str, api_version: str, logger: Optional[logging.Logger] = None):
        self._system_token = access_token
        self.api_version = api_version
        self.base = f"{GRAPH_HOST}/{api_version}"
        self.logger = logger or logging.getLogger("airbyte")
        self.session = requests.Session()
        self._page_tokens: Dict[str, str] = {}

    # ---------- tokens ----------

    def page_token(self, page_id: str) -> str:
        """Deriva o Page Access Token. Edge de página recusa token de System User."""
        if page_id not in self._page_tokens:
            data = self._request("GET", page_id, params={"fields": "access_token"}, token=self._system_token)
            token = data.get("access_token")
            if not token:
                raise GraphAPIError(
                    {"message": f"A página {page_id} não devolveu access_token. Confirme se o System "
                                f"User tem acesso a ela no Business Manager.", "code": 190},
                )
            self._page_tokens[page_id] = token
            self.logger.info(f"Page Access Token derivado para a página {page_id}")
        return self._page_tokens[page_id]

    # ---------- transporte ----------

    def _sleep_for(self, response: Optional[requests.Response], attempt: int) -> float:
        """Backoff lendo o header de uso; só cai no exponencial quando o header não ajuda."""
        wait = min(2 ** attempt, 60)
        if response is not None:
            raw = response.headers.get("x-business-use-case-usage")
            if raw:
                try:
                    for entries in json.loads(raw).values():
                        for entry in entries:
                            estimated = entry.get("estimated_time_to_regain_access") or 0
                            if estimated:
                                wait = max(wait, min(float(estimated) * 60, 600))
                except (ValueError, AttributeError):
                    pass
        return wait

    @staticmethod
    def _halve_page_size(url: str, payload: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """A Graph API responde 500 quando a página pedida é grande demais para a edge.

        Acontece em `video_reels`: a mensagem é "reduce the amount of data". Em vez de
        falhar, o cliente reduz o tamanho da página — inclusive em URL de paginação, onde
        o `limit` vem embutido.
        """
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        if "limit" in payload:
            current = int(payload["limit"])
            if current <= MIN_PAGE_SIZE:
                return None
            payload = {**payload, "limit": max(MIN_PAGE_SIZE, current // 2)}
            return url, payload
        if "limit" in query:
            current = int(query["limit"])
            if current <= MIN_PAGE_SIZE:
                return None
            query["limit"] = str(max(MIN_PAGE_SIZE, current // 2))
            return urlunparse(parsed._replace(query=urlencode(query))), payload
        return None

    def _request(self, method: str, path: str, token: str,
                 params: Optional[Mapping[str, Any]] = None,
                 data: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base}/{path}"
        payload = dict(params or {})
        payload["access_token"] = token
        last_error: Optional[Mapping[str, Any]] = None

        for attempt in range(MAX_RETRIES):
            try:
                if method == "GET":
                    response = self.session.get(url, params=payload, timeout=120)
                else:
                    response = self.session.post(url, data={**payload, **(data or {})}, timeout=120)
            except requests.RequestException as exc:
                wait = min(2 ** attempt, 60)
                self.logger.warning(f"Falha de rede ({redact(exc)}); nova tentativa em {wait}s")
                time.sleep(wait)
                continue

            if response.status_code == 200:
                return response.json()

            try:
                last_error = response.json().get("error", {})
            except ValueError:
                last_error = {"message": response.text[:500], "code": response.status_code}

            code = last_error.get("code")
            if OVERSIZED_HINT in last_error.get("message", ""):
                smaller = self._halve_page_size(url, payload)
                if smaller:
                    url, payload = smaller
                    size = payload.get("limit") or dict(parse_qsl(urlparse(url).query)).get("limit")
                    self.logger.info(f"Página grande demais em {redact(path)}; reduzindo limit para {size}")
                    continue
            if code in RATE_LIMIT_CODES:
                wait = self._sleep_for(response, attempt)
                self.logger.warning(
                    f"Limite de uso em {redact(path)} (code={code}); aguardando {wait:.0f}s"
                )
                time.sleep(wait)
                continue
            if response.status_code in TRANSIENT_STATUSES:
                wait = min(2 ** attempt, 60)
                self.logger.warning(
                    f"Erro transitório {response.status_code} (code={code}) em {redact(path)}; "
                    f"tentativa {attempt + 1} de {MAX_RETRIES} em {wait:.0f}s"
                )
                time.sleep(wait)
                continue
            raise GraphAPIError(last_error, context=f"{redact(path)}: ")

        raise GraphAPIError(
            last_error or {"message": "esgotadas as tentativas"}, context=f"{redact(path)}: "
        )

    def get(self, path: str, token: str, **params: Any) -> Dict[str, Any]:
        return self._request("GET", path, token=token, params=params)

    def paginate(self, path: str, token: str, max_pages: int = 1000, **params: Any) -> Iterable[Dict[str, Any]]:
        """Segue o cursor `next` da Graph API, devolvendo registro a registro."""
        page = self._request("GET", path, token=token, params=params)
        pages = 0
        while True:
            for record in page.get("data", []):
                yield record
            next_url = (page.get("paging") or {}).get("next")
            pages += 1
            if not next_url or pages >= max_pages:
                return
            page = self._request("GET", next_url, token=token)

    def batch(self, relative_urls: List[str], token: str) -> List[Optional[Dict[str, Any]]]:
        """Até 50 sub-requests numa chamada. Devolve None onde o sub-request falhou."""
        results: List[Optional[Dict[str, Any]]] = []
        for start in range(0, len(relative_urls), BATCH_SIZE):
            chunk = relative_urls[start:start + BATCH_SIZE]
            payload = json.dumps([{"method": "GET", "relative_url": url} for url in chunk])
            raw = self._request("POST", "", token=token, data={"batch": payload})
            for item in raw if isinstance(raw, list) else []:
                if not item or item.get("code") != 200:
                    results.append(None)
                    continue
                try:
                    results.append(json.loads(item["body"]))
                except (ValueError, KeyError):
                    results.append(None)
        return results

    # ---------- insights ----------

    def insights(self, object_id: str, token: str, metrics: List[str], edge: str = "insights",
                 **params: Any) -> List[Dict[str, Any]]:
        """Pede a lista de métricas; se a API recusar o lote, isola e descarta a métrica morta.

        Métrica inválida derruba o request inteiro e a mensagem de erro não diz qual é —
        por isso o fallback um a um, feito uma vez só por lista.
        """
        try:
            return self.get(f"{object_id}/{edge}", token=token, metric=",".join(metrics), **params).get("data", [])
        except GraphAPIError as exc:
            if exc.code != INVALID_METRIC_CODE or len(metrics) == 1:
                if exc.code == INVALID_METRIC_CODE:
                    self.logger.warning(f"Métrica recusada e descartada: {metrics[0]} ({exc.message})")
                    return []
                raise
        data: List[Dict[str, Any]] = []
        for metric in metrics:
            data.extend(self.insights(object_id, token, [metric], edge=edge, **params))
        return data
