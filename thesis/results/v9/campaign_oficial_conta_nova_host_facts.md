# Fatos dos 12 hosts da campanha oficial v9 (conta nova) -- auditoria somente leitura, pré-teardown

Coletado via SSH (chave do operador só para o host de controle; chave de campanha, já presente em `~/.ssh/campaign_key` no controle, para os outros 11) em 2026-11-16, antes de qualquer decisão sobre desmontagem da frota. Nenhum comando abaixo alterou qualquer host. IDs de conta AWS nunca aparecem (só os outputs do Terraform já listados abaixo, sem `account_id`); nenhum conteúdo de chave foi lido.

## Outputs não sensíveis do Terraform (IPs/regiões -- `terraform output -json inventory`, campo `campaign_private_key` nunca lido por este documento)

| Papel | Rótulo | Região | IP privado | IP público |
|---|---|---|---|---|
| control | control | sa-east-1 | 172.31.25.65 | <fleet-ip-control> |
| server | sa-east-1 | sa-east-1 | 172.31.5.195 | <fleet-ip-server-sa-east-1> |
| server | us-east-1 | us-east-1 | 172.31.14.117 | <fleet-ip-server-us-east-1> |
| server | ap-northeast-1 | ap-northeast-1 | 172.31.15.122 | <fleet-ip-server-ap-northeast-1> |
| client | L0-sa-east-1 | sa-east-1 (colocado) | 172.31.2.133 | <fleet-ip-client-L0-sa-east-1> |
| client | L123 | ca-central-1 | 172.31.11.49 | <fleet-ip-client-L123> |
| client | L219 | eu-north-1 | 172.31.43.183 | <fleet-ip-client-L219> |
| client | L325 | ap-southeast-1 | 172.31.38.214 | <fleet-ip-client-L325> |
| client | L0-us-east-1 | us-east-1 (colocado) | 172.31.5.229 | <fleet-ip-client-L0-us-east-1> |
| client | L14 | ca-central-1 | 172.31.14.106 | <fleet-ip-client-L14> |
| client | L0-ap-northeast-1 | ap-northeast-1 (colocado) | 172.31.15.45 | <fleet-ip-client-L0-ap-northeast-1> |
| client | L30 | ap-northeast-2 | 172.31.20.188 | <fleet-ip-client-L30> |

## Fatos por host

| Papel | Host | AMI | Tipo de instância | Kernel | Docker | tshark | chrony (pacote) | CPUs |
|---|---|---|---|---|---|---|---|---:|
| control | control | ami-027c2612cea3ab019 | t4g.micro | 6.1.189-236.400.amzn2023 **aarch64** | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| server | sa-east-1 | ami-0947d58e57fa20c5f | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| server | us-east-1 | ami-0cf4b3ccd41c5a321 | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| server | ap-northeast-1 | ami-04ff541c93bef7350 | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L0-sa-east-1 | ami-0947d58e57fa20c5f | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L123 | ami-0f39320fcf308a07f | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L219 | ami-072b92f3846437950 | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L325 | ami-0e5c4d93500d698da | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L0-us-east-1 | ami-0cf4b3ccd41c5a321 | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L14 | ami-0f39320fcf308a07f | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L0-ap-northeast-1 | ami-04ff541c93bef7350 | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |
| client | L30 | ami-0bef747b3acf85e8f | m7i-flex.large | 6.1.189-236.400.amzn2023 x86_64 | 25.0.14 (pkg 25.0.18-1) | não instalado | 4.3-1.amzn2023.0.6 | 2 |

**Memória (free -h, "total"):** control 916Mi (t4g.micro); todos os 11 demais hosts (servidores+clientes, m7i-flex.large) 7,6Gi -- idêntico entre todos os hosts do mesmo tipo de instância, sem exceção.

**`ip route` (rota default + sub-rede):** todos os 11 hosts m7i-flex.large usam a mesma interface `enp39s0` com o mesmo padrão `/20` (gateway `.0.1` ou `.16.1`/`.32.1` conforme a sub-rede VPC de cada região) -- idêntico em forma entre hosts do mesmo papel, divergindo apenas no octeto esperado (IP privado de cada host, já tabelado acima). O controle usa `ens5` (nome de interface diferente, esperado -- é um tipo de instância Graviton/ARM diferente, t4g.micro).

**`tc qdisc show`:** idêntico em todos os 12 hosts -- `fq_codel` na interface principal (parâmetros idênticos: `limit 10240p flows 1024 quantum 9015 target 5ms interval 100ms memory_limit 32Mb ecn drop_batch 64`), mais filas `noqueue` para `lo`/`docker0`/pontes de rede dos containers. Nenhuma diferença de QoS entre hosts do mesmo papel.

**Sysctls `net.ipv4.tcp_*` relevantes (idêntico nos 12 hosts, sem exceção):**
```
net.ipv4.tcp_congestion_control = cubic
net.ipv4.tcp_slow_start_after_idle = 1
net.ipv4.tcp_rmem = 4096  131072  6291456
net.ipv4.tcp_wmem = 4096  20480   4194304
net.ipv4.tcp_fastopen = 1
net.ipv4.tcp_timestamps = 1
```

**`chronyc tracking` (estado do relógio):** todos os 12 hosts sincronizados contra a mesma referência (`A9FEA97B`, o serviço de tempo da AWS via link-local `169.254.169.123`), `Leap status: Normal` em todos, offsets medidos na ordem de poucos microssegundos ou menos em todos os 12 (o maior offset observado foi ~4,1µs no servidor sa-east-1; o menor, <0,3µs no cliente L325) -- nenhum host fora de sincronismo.

## Divergências encontradas entre hosts do mesmo papel

**Nenhuma**, além das esperadas pelo próprio desenho da topologia (AMI id e endereço IP diferem por região -- cada região AWS publica uma AMI própria para a mesma imagem-base `amzn2023`; isso não é uma divergência de configuração, é inerente a rodar em 7 regiões diferentes). Versão de kernel, Docker, chrony, ausência de `tshark`/`wireshark-common` no sistema (a campanha usa sua própria dependência de captura, não o pacote de sistema), `tc qdisc`, e todos os sysctls TCP auditados são **byte-a-byte idênticos** em:
- todos os 3 servidores entre si;
- todos os 8 clientes entre si;
- servidores e clientes entre si (mesmo tipo de instância `m7i-flex.large`, mesmo kernel/pacotes).

O host de controle (`t4g.micro`, ARM Graviton, papel único -- nunca comparado a outro do mesmo papel porque não há outro) difere do esperado apenas pelo tipo de instância (CPU/memória menores, nome de interface de rede diferente) -- consistente com seu papel de orquestração apenas, nunca parte de nenhum fluxo medido.

## Estado da infraestrutura no momento desta auditoria

12 instâncias no ar, nenhuma parada/alterada por esta auditoria (somente leitura). Esta auditoria é o pré-requisito explicitamente exigido antes de qualquer decisão sobre teardown -- nenhuma ação de desmontagem foi tomada nesta rodada.
