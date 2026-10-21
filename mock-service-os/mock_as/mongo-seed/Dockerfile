FROM mongo@sha256:dc28ed5a9d0fc616903c3f463bb1e53b92b49f441721b91926e87d90bf957ce8

COPY init_clients.json /init_clients.json
COPY init_accounts.json /init_accounts.json
COPY init_credentials.json /init_credentials.json

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD /start.sh "my-replica-set/mongo3:30003,mongo2:30002,mongo1:30001"