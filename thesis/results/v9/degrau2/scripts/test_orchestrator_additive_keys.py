#!/usr/bin/env python3
"""Degrau 2, Etapa 0, item 2: teste local da mudanca aditiva em
orchestrator.py's run_execution() -- confirma que as duas chaves novas
(`t_fluxo_fino_seconds`/`phase_accounting`) aparecem corretamente no
dict final, sem quebrar nada existente, usando um `result` SIMULADO
(mock -- nunca uma execucao real/SSH). Replica exatamente a expressao
adicionada ao dict de retorno real (`result.get("t_fluxo_seconds")` e
`result.get("phase_accounting", {})`), nunca chamando a classe real do
orquestrador (que exige SSH/estado de campanha)."""


def build_return_dict_fragment(result: dict) -> dict:
    """Replica EXATA da fatia nova do dict de retorno de run_execution()
    -- so as duas chaves aditivas, para teste isolado."""
    return {
        "t_fluxo_fino_seconds": result.get("t_fluxo_seconds"),
        "phase_accounting": result.get("phase_accounting", {}),
    }


def test_com_campos_novos_presentes():
    """Simula o stdout real de campaign_client_runner.py (via
    latency_automation.run_once_timed()), COM os campos novos."""
    result_mock = {
        "calls": [{"latency_ms": 123.4}, {"latency_ms": 98.7}],
        "t_fluxo_seconds": 2.357881,
        "phase_accounting": {
            "http_calls_seconds": 0.4753, "signing_seconds": 0.0012,
            "verification_seconds": 0.0034, "explicit_wait_seconds": 0.0,
            "setup_seconds": 0.0, "accounted_seconds": 0.4799,
            "residual_seconds": 1.878, "residual_pct_of_t_fluxo": 79.6,
        },
        "whole_run_retries": [],
    }
    extra = build_return_dict_fragment(result_mock)
    assert extra["t_fluxo_fino_seconds"] == 2.357881, extra
    assert extra["phase_accounting"]["residual_seconds"] == 1.878, extra
    assert set(extra["phase_accounting"].keys()) == set(result_mock["phase_accounting"].keys())
    print("OK: campos novos presentes e corretos quando result os tem.")


def test_sem_campos_novos_nunca_quebra():
    """Simula um `result` ANTIGO (sem t_fluxo_seconds/phase_accounting --
    ex. uma versao hipotetica mais velha de campaign_client_runner.py) --
    confirma que `.get()` com default nunca levanta excecao, so devolve
    None/{} (backward-compatible, nunca quebra o dict de retorno)."""
    result_mock_antigo = {"calls": [], "whole_run_retries": []}
    extra = build_return_dict_fragment(result_mock_antigo)
    assert extra["t_fluxo_fino_seconds"] is None, extra
    assert extra["phase_accounting"] == {}, extra
    print("OK: ausencia dos campos novos nunca quebra, degrada pra None/{} .")


def test_chaves_existentes_do_dict_completo_nao_mudam():
    """Confirma que a mudanca e PURAMENTE aditiva no NIVEL do dict
    completo -- simula o dict de retorno INTEIRO (todas as chaves
    existentes + as 2 novas) e confirma que nenhuma chave existente foi
    removida/renomeada (mesmo conjunto de chaves de antes, + as 2 novas)."""
    chaves_existentes_antes_desta_mudanca = {
        "insurance", "person", "gateway_log_lines", "curveID", "dualAuthenticated",
        "tlsVersion", "handshake_bytes_per_connection", "start_utc", "end_utc",
        "cpu_client", "cpu_server", "retry_attempts", "retry_failures",
        "network_transport_retries",
    }
    dict_completo_simulado = {
        "insurance": [], "person": [], "gateway_log_lines": [], "curveID": "X",
        "dualAuthenticated": False, "tlsVersion": "1.3", "handshake_bytes_per_connection": [],
        "start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-01-01T00:00:01Z",
        "cpu_client": {}, "cpu_server": {}, "retry_attempts": 1, "retry_failures": [],
        "network_transport_retries": [],
        **build_return_dict_fragment({"t_fluxo_seconds": 1.0, "phase_accounting": {}}),
    }
    assert chaves_existentes_antes_desta_mudanca.issubset(set(dict_completo_simulado.keys()))
    novas = set(dict_completo_simulado.keys()) - chaves_existentes_antes_desta_mudanca
    assert novas == {"t_fluxo_fino_seconds", "phase_accounting"}, novas
    print("OK: todas as chaves existentes preservadas; so 2 chaves novas adicionadas.")


def build_execucao_entry_fragment(result: dict) -> dict:
    """Replica EXATA da fatia nova de `execucao_entry`/`aquecimento_entry`
    dentro de run_pilot() -- a segunda camada de serializacao, SEPARADA
    do dict de retorno de run_execution(), que e a que de fato grava em
    disco (runs_raw/*.json, piloto_calls.json, aquecimento_execucoes.json).
    Achado real (pos-campanha, 2026-11-17): a mudanca original da Etapa 0
    tocou SO em run_execution() -- o teste acima (`test_*_presentes` etc.)
    cobria so essa camada. Esta camada aqui e distinta e tinha, antes
    desta correcao, sua PROPRIA lista fixa de chaves que nunca incluia as
    2 novas -- por isso os dois campos nunca apareceram em nenhum arquivo
    das 2 rodadas reais ja coletadas (ver relato ao usuario)."""
    return {
        "t_fluxo_fino_seconds": result.get("t_fluxo_fino_seconds"),
        "phase_accounting": result.get("phase_accounting", {}),
    }


def test_execucao_entry_tambem_preserva_campos_novos():
    """Regressao direta do achado real: `result` aqui simula o que
    run_execution() JA DEVOLVE (apos a correcao da Etapa 0, incluindo as
    2 chaves novas) -- confirma que a camada de persistencia
    (execucao_entry/aquecimento_entry) tambem as repassa, em vez de
    descarta-las silenciosamente como acontecia antes desta correcao."""
    run_execution_return_mock = {
        "insurance": [], "person": [], "gateway_log_lines": [],
        "t_fluxo_fino_seconds": 2.357881,
        "phase_accounting": {"signing_seconds": 0.0012, "residual_seconds": 1.878},
    }
    extra = build_execucao_entry_fragment(run_execution_return_mock)
    assert extra["t_fluxo_fino_seconds"] == 2.357881, extra
    assert extra["phase_accounting"]["residual_seconds"] == 1.878, extra
    print("OK: execucao_entry/aquecimento_entry tambem preservam os campos novos.")


if __name__ == "__main__":
    test_com_campos_novos_presentes()
    test_sem_campos_novos_nunca_quebra()
    test_chaves_existentes_do_dict_completo_nao_mudam()
    test_execucao_entry_tambem_preserva_campos_novos()
    print("TODOS OS TESTES PASSARAM (mock local, nenhuma execucao real/SSH).")
