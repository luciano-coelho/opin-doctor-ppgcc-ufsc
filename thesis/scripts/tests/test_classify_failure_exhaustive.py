"""Decisao 161 (correcao de item 1, pedido do Luciano apos a reauditoria
da tag v6): teste parametrizado EXAUSTIVO de classify_failure() contra
TODAS as classes de requests.exceptions da versao pinada (requests==
2.32.5), TODAS as classes relevantes de urllib3.exceptions, e as
excecoes de socket/ssl/builtin relevantes -- com o veredito de cada
uma. Sem isso, um `isinstance()` que caia certo nos poucos casos
testados a mao pode esconder uma subclasse mal classificada (foi
exatamente isso que a reauditoria achou: SSLError/ProxyError sao
subclasses de ConnectionError e passavam como "network_transport").

Este arquivo nao confia em nenhuma lista "conhecida boa" escrita a
mao -- ele introspecciona os modulos reais (requests.exceptions,
urllib3.exceptions) em tempo de execucao, constroi uma instancia de
CADA classe de excecao exportada, e verifica o veredito contra
`latency_automation._NETWORK_TRANSPORT_EXACT_TYPES` (a fonte da
verdade, nunca duplicada aqui)."""
import inspect
import socket
import ssl
import sys
from pathlib import Path

import pytest
import requests.exceptions as req_exc
import urllib3.exceptions as u3_exc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import latency_automation as la
import opin_flow as of

# Classes explicitamente NAO testadas aqui porque nao sao excecoes de
# falha real (avisos/infra) -- nunca excluidas por "nao bater o
# veredito esperado", so por nao serem o tipo de objeto que um
# classify_failure() real algum dia receberia.
_WARNING_OR_INFRA_NAMES = {
    "RequestsWarning", "FileModeWarning", "RequestsDependencyWarning", "BaseHTTPError",
}
_U3_WARNING_NAMES = {
    "HTTPWarning", "InsecurePlatformWarning", "InsecureRequestWarning",
    "SecurityWarning", "SystemTimeWarning", "NotOpenSSLWarning", "DependencyWarning",
}


class _FakeHTTPResponseForChunkLength:
    """So pro construtor de urllib3.exceptions.InvalidChunkLength, que
    chama response.tell() e le response.length_remaining -- nunca
    alcancado de verdade por classify_failure() (urllib3 nunca deixa
    isto escapar pra fora de requests), construido so pra o teste
    exaustivo conseguir instanciar a classe e confirmar o veredito."""
    def tell(self):
        return 0
    length_remaining = 0


_SPECIAL_CONSTRUCTORS = {
    "requests.exceptions.JSONDecodeError": lambda cls: cls("msg", "doc", 0),
    "requests.exceptions.CompatJSONDecodeError": lambda cls: cls("msg", "doc", 0),
    "urllib3.exceptions.InvalidChunkLength": lambda cls: cls(_FakeHTTPResponseForChunkLength(), b"xyz"),
}


def _construct(cls, qualname=None):
    """Tenta instanciar `cls` com o minimo de esforco -- mensagem unica,
    depois sem args, depois preenchendo cada parametro posicional
    obrigatorio com um valor generico. Levanta se nada funcionar (o
    teste entao reporta esse caso explicitamente, nunca o esconde)."""
    if qualname in _SPECIAL_CONSTRUCTORS:
        return _SPECIAL_CONSTRUCTORS[qualname](cls)
    for attempt in ("synthetic test message", None):
        try:
            return cls(attempt) if attempt is not None else cls()
        except TypeError:
            continue
    sig = inspect.signature(cls.__init__)
    required = [
        p for name, p in sig.parameters.items()
        if name != "self" and p.default is p.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    for filler in ("synthetic", 0, None):
        try:
            return cls(*([filler] * len(required)))
        except Exception:
            continue
    raise TypeError(f"could not construct {cls.__name__} with any generic strategy")


def _collect_requests_exception_classes():
    out = []
    for name in sorted(dir(req_exc)):
        if name.startswith("_") or name in _WARNING_OR_INFRA_NAMES:
            continue
        obj = getattr(req_exc, name)
        if inspect.isclass(obj) and issubclass(obj, Exception) and not issubclass(obj, Warning):
            out.append((f"requests.exceptions.{name}", obj))
    return out


def _collect_urllib3_exception_classes():
    out = []
    for name in sorted(dir(u3_exc)):
        if name.startswith("_") or name in _U3_WARNING_NAMES:
            continue
        obj = getattr(u3_exc, name)
        if inspect.isclass(obj) and issubclass(obj, BaseException) and not issubclass(obj, Warning):
            out.append((f"urllib3.exceptions.{name}", obj))
    return out


def _collect_builtin_and_ssl_classes():
    return [
        ("builtins.ConnectionError", ConnectionError),
        ("builtins.ConnectionResetError", ConnectionResetError),
        ("builtins.ConnectionRefusedError", ConnectionRefusedError),
        ("builtins.ConnectionAbortedError", ConnectionAbortedError),
        ("builtins.BrokenPipeError", BrokenPipeError),
        ("builtins.TimeoutError", TimeoutError),
        ("socket.timeout (alias of TimeoutError)", socket.timeout),
        ("ssl.SSLError", ssl.SSLError),
        ("ssl.SSLCertVerificationError", ssl.SSLCertVerificationError),
        ("ssl.SSLZeroReturnError", ssl.SSLZeroReturnError),
        ("builtins.OSError (generic)", OSError),
        ("builtins.ValueError (unrelated, must fail_closed)", ValueError),
    ]


def _expected_verdict(cls, qualname=None) -> str:
    """A fonte da verdade e a classify_failure() REAL, chamada com uma
    instancia real -- nunca uma tabela escrita a mao em paralelo (que
    poderia divergir da implementacao sem o teste notar)."""
    return la.classify_failure(_construct(cls, qualname))


ALL_CASES = (
    _collect_requests_exception_classes()
    + _collect_urllib3_exception_classes()
    + _collect_builtin_and_ssl_classes()
)

# Os UNICOS tipos que devem sair "network_transport" -- tudo o mais,
# nas 3 fontes acima, tem que ser "fail_closed". Lista literal (nao
# importada de latency_automation) de proposito: se alguem ampliar
# _NETWORK_TRANSPORT_EXACT_TYPES sem querer, este teste tem que
# reprovar em vez de silenciosamente concordar com a mudanca.
_EXPECTED_NETWORK_TRANSPORT_QUALNAMES = {
    "requests.exceptions.ConnectionError",
    "requests.exceptions.ConnectTimeout",
    "requests.exceptions.ReadTimeout",
    "requests.exceptions.Timeout",
    "builtins.ConnectionError",
    "builtins.ConnectionResetError",
    "builtins.ConnectionRefusedError",
    "builtins.ConnectionAbortedError",
    "builtins.BrokenPipeError",
    "builtins.TimeoutError",
    "socket.timeout (alias of TimeoutError)",
}


@pytest.mark.parametrize("qualname,cls", ALL_CASES, ids=[c[0] for c in ALL_CASES])
def test_classify_failure_exhaustive_verdict_table(qualname, cls):
    verdict = _expected_verdict(cls, qualname)
    expected = "network_transport" if qualname in _EXPECTED_NETWORK_TRANSPORT_QUALNAMES else "fail_closed"
    assert verdict == expected, (
        f"{qualname}: classify_failure() devolveu {verdict!r}, esperado {expected!r} -- "
        f"veja Decisao 161 (SSLError/ProxyError sao subclasses de ConnectionError e NAO "
        f"devem ser network_transport, mesmo com heranca)."
    )


def test_sslerror_and_proxyerror_are_explicitly_fail_closed():
    """Regressao direta do achado da reauditoria -- as DUAS sao
    subclasses de requests.exceptions.ConnectionError."""
    assert issubclass(req_exc.SSLError, req_exc.ConnectionError)
    assert issubclass(req_exc.ProxyError, req_exc.ConnectionError)
    assert la.classify_failure(req_exc.SSLError("cert verify failed")) == "fail_closed"
    assert la.classify_failure(req_exc.ProxyError("upstream proxy failure")) == "fail_closed"


def test_unknown_exception_still_fail_closed():
    class TotallyUnknownException(Exception):
        pass
    assert la.classify_failure(TotallyUnknownException("???")) == "fail_closed"


def test_signature_verification_error_still_fail_closed():
    assert la.classify_failure(of.SignatureVerificationError("tampered")) == "fail_closed"


def test_bare_connection_error_and_timeout_are_network_transport():
    assert la.classify_failure(req_exc.ConnectionError("reset")) == "network_transport"
    assert la.classify_failure(req_exc.ConnectTimeout("connect timed out")) == "network_transport"
    assert la.classify_failure(req_exc.ReadTimeout("read timed out")) == "network_transport"
    assert la.classify_failure(ConnectionResetError("reset by peer")) == "network_transport"


def test_coverage_is_non_trivial():
    """Guarda contra um teste que, por algum bug de introspeccao, acabe
    rodando sobre zero/poucas classes sem ningum notar."""
    assert len(ALL_CASES) >= 40, f"esperava introspeccionar pelo menos 40 classes, achou {len(ALL_CASES)}"
