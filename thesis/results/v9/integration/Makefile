.PHONY: t5 clean

t5:
	bash run_t5.sh

clean:
	rm -rf gateway/certs proxy/certs
	docker network rm mockopin-v9-net >/dev/null 2>&1 || true
