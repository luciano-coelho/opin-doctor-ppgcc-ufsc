FROM golang:1.23
# iproute2 (tc/netem) + iputils-ping: used by thesis/scripts/set_latency.sh
# to inject and verify artificial WAN latency for Experiment 1. Not needed
# for normal gateway operation.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Download Go modules
# COPY certs /app/certs
COPY go.mod ./
COPY go.sum ./
# Copy the entrypoint script into the container
COPY entrypoint.sh ./
# Copy the source code. Note the slash at the end, as explained in
# https://docs.docker.com/reference/dockerfile/#copy
COPY *.go ./
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /mtls_go
# Make the entrypoint script executable
RUN chmod +x ./entrypoint.sh
EXPOSE 443

ENTRYPOINT ["./entrypoint.sh"]
# Run
CMD ["/mtls_go"]