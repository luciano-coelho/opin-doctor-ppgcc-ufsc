# v9: gera os certificados dos 4 perfis em tempo de execucao, nunca
# commitados daqui para frente (ver DECISIONS.md, Decisao 11, e
# certs/.gitignore). Testes locais e a T5 usam `make certs` (loopback,
# o default); a campanha real usa `make certs SERVER_IPS=... SERVER_DNS=...`
# com os enderecos reais da frota, resolvidos no deploy -- nunca
# versionados, nem aqui nem em outro lugar.

IMAGE := mockopin-v9-certs
# OUT e distinto de "certs/" (o diretorio ja rastreado com o registro
# historico da T4) de proposito: evita que `make certs` colida com, ou
# aninhe dentro de, esse registro -- ver DECISIONS.md, Decisao 11.
OUT   := generated
SERVER_DNS ?= mtls,auth.local,matls-auth.local,api.local,matls-api.local,directory,directory.local,keystore
SERVER_IPS ?= 127.0.0.1,::1
CLIENT_DNS ?= opin-client-one

.PHONY: certs clean

certs:
	docker build --build-arg SERVER_DNS="$(SERVER_DNS)" --build-arg SERVER_IPS="$(SERVER_IPS)" --build-arg CLIENT_DNS="$(CLIENT_DNS)" -t $(IMAGE) .
	-docker rm -f $(IMAGE)-run >/dev/null 2>&1
	rm -rf $(OUT)
	docker create --name $(IMAGE)-run $(IMAGE)
	docker cp $(IMAGE)-run:/app/certs $(OUT)
	docker cp $(IMAGE)-run:/report.txt $(OUT)/validation_report.txt
	docker rm $(IMAGE)-run >/dev/null
	@echo "Certificados gerados em ./$(OUT)/ -- efemero, nunca commitado (ver $(OUT)/.gitignore). Relatorio em $(OUT)/validation_report.txt."

clean:
	rm -rf $(OUT)
