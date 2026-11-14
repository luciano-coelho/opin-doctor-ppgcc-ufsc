"""Decisao 158 (item 6a, autorizado pelo autor): testes da
classificacao de falha em latency_automation.py -- "network_transport"
(retry da execucao inteira, no maximo NETWORK_TRANSPORT_MAX_ATTEMPTS
vezes) contra "fail_closed" (aborta na hora, sem retry, por exclusao --
nunca uma lista positiva de "excecoes que abortam"). Injeta excecoes de
cada classe via monkeypatch de run_once_timed() -- nunca depende do
stack real (sem docker, sem rede)."""
import sys
from pathlib import Path
from unittest import mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import latency_automation as la
import opin_flow as of


def _http_error(status_code):
    resp = requests.Response()
    resp.status_code = status_code
    return requests.exceptions.HTTPError(f"{status_code} error", response=resp)


class _UnknownException(Exception):
    """Representa qualquer excecao NAO classificada -- nem rede, nem
    criptografia/assinatura, nem HTTPError. Deve cair em fail_closed
    por exclusao, nunca precisar entrar numa lista positiva."""


# ---- classify_failure(): unit tests diretos ----

@pytest.mark.parametrize("exc", [
    requests.exceptions.ConnectionError("reset"),
    requests.exceptions.Timeout("timed out"),
    ConnectionError("refused"),
    ConnectionResetError("reset by peer"),
    _http_error(502),
    _http_error(504),
])
def test_classify_network_transport(exc):
    assert la.classify_failure(exc) == "network_transport"


@pytest.mark.parametrize("exc", [
    of.SignatureVerificationError("bad signature"),
    _http_error(400),
    _http_error(500),
    _UnknownException("something nobody classified"),
    RuntimeError("generic runtime error"),
])
def test_classify_fail_closed(exc):
    assert la.classify_failure(exc) == "fail_closed"


# ---- run_once_timed_with_retry(): comportamento injetado ----

def test_network_transport_retries_then_succeeds():
    calls = []

    def fake_run_once_timed(crypto_profile, return_calls=False):
        calls.append(1)
        if len(calls) < la.NETWORK_TRANSPORT_MAX_ATTEMPTS:
            raise requests.exceptions.ConnectionError("reset by peer")
        return {"t_fluxo_seconds": 1.0}

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        result = la.run_once_timed_with_retry("classico", "run01", whole_run_retries)

    assert result == {"t_fluxo_seconds": 1.0}
    assert len(calls) == la.NETWORK_TRANSPORT_MAX_ATTEMPTS
    assert len(whole_run_retries) == la.NETWORK_TRANSPORT_MAX_ATTEMPTS - 1
    assert all(e["failure_class"] == "network_transport" for e in whole_run_retries)
    assert all(e["profile"] == "classico" and e["run"] == "run01" for e in whole_run_retries)
    assert all("at_utc" in e and "error" in e for e in whole_run_retries)


def test_retry_entry_has_full_exception_text_reason_and_both_timestamps():
    """Decisao 163 (item 2): retries_report precisa do texto completo
    da excecao (nao so a mensagem externa), do motivo da classificacao
    em prosa, e do horario de INICIO e de CAPTURA de cada tentativa
    descartada."""
    def fake_run_once_timed(crypto_profile, return_calls=False):
        raise requests.exceptions.ConnectionError("reset by peer")

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        with pytest.raises(SystemExit):
            la.run_once_timed_with_retry("classico", "run07", whole_run_retries)

    assert len(whole_run_retries) == la.NETWORK_TRANSPORT_MAX_ATTEMPTS
    for e in whole_run_retries:
        assert e["error"] == repr(requests.exceptions.ConnectionError("reset by peer"))
        assert "ConnectionError" in e["classification_reason"]
        assert "_NETWORK_TRANSPORT_EXACT_TYPES" in e["classification_reason"]
        assert "attempt_started_at_utc" in e and "at_utc" in e
        assert e["attempt_started_at_utc"] <= e["at_utc"]


def test_network_transport_exhausts_all_attempts_aborts():
    calls = []

    def fake_run_once_timed(crypto_profile, return_calls=False):
        calls.append(1)
        raise requests.exceptions.ConnectionError("reset by peer")

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        with pytest.raises(SystemExit):
            la.run_once_timed_with_retry("classico", "run02", whole_run_retries)

    assert len(calls) == la.NETWORK_TRANSPORT_MAX_ATTEMPTS
    assert len(whole_run_retries) == la.NETWORK_TRANSPORT_MAX_ATTEMPTS
    assert all(e["failure_class"] == "network_transport" for e in whole_run_retries)


def test_fail_closed_signature_error_aborts_immediately_no_retry():
    calls = []

    def fake_run_once_timed(crypto_profile, return_calls=False):
        calls.append(1)
        raise of.SignatureVerificationError("tampered")

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        with pytest.raises(of.SignatureVerificationError):
            la.run_once_timed_with_retry("pqc", "run03", whole_run_retries)

    assert len(calls) == 1, "fail_closed nunca deve ser retried"
    assert len(whole_run_retries) == 1
    assert whole_run_retries[0]["failure_class"] == "fail_closed"


def test_fail_closed_unexpected_business_http_error_aborts_immediately():
    calls = []

    def fake_run_once_timed(crypto_profile, return_calls=False):
        calls.append(1)
        raise _http_error(500)

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        with pytest.raises(requests.exceptions.HTTPError):
            la.run_once_timed_with_retry("hibrido-and", "run04", whole_run_retries)

    assert len(calls) == 1
    assert whole_run_retries[0]["failure_class"] == "fail_closed"


def test_unknown_exception_aborts_without_retry():
    """A excecao desconhecida tem que abortar -- fail_closed por
    exclusao, nunca por estar numa lista positiva de tipos conhecidos."""
    calls = []

    def fake_run_once_timed(crypto_profile, return_calls=False):
        calls.append(1)
        raise _UnknownException("nobody classified this")

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        with pytest.raises(_UnknownException):
            la.run_once_timed_with_retry("hibrido-v8", "run05", whole_run_retries)

    assert len(calls) == 1, "excecao desconhecida nunca deve ser retried"
    assert len(whole_run_retries) == 1
    assert whole_run_retries[0]["failure_class"] == "fail_closed"


def test_success_on_first_attempt_no_retries_recorded():
    def fake_run_once_timed(crypto_profile, return_calls=False):
        return {"t_fluxo_seconds": 0.5}

    whole_run_retries = []
    with mock.patch.object(la, "run_once_timed", side_effect=fake_run_once_timed):
        result = la.run_once_timed_with_retry("classico", "run06", whole_run_retries)

    assert result == {"t_fluxo_seconds": 0.5}
    assert whole_run_retries == []
