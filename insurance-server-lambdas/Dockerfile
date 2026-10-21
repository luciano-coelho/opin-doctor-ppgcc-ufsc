FROM gradle:5.3.1-jdk11-slim@sha256:4fdc356e8b325a12bd03d5672ca56eb9f8db862fcd24eafaaa06aca5e8397741 as builder
COPY --chown=gradle:gradle . /home/application
WORKDIR /home/application
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY
ARG AWS_SESSION_TOKEN
RUN gradle build -x test --no-daemon

FROM amazonlinux:2@sha256:f86b99704b49b2fde6bf42b4c5257fcb0b1e0946509da5d6cea08c4227618433 as graalvm
# install graal to amazon linux.
ENV LANG=en_US.UTF-8


RUN yum install -y gcc gcc-c++ libc6-dev  zlib1g-dev curl bash zlib zlib-devel zip tar gzip \
    && rm -rf /var/cache/yum

ENV GRAAL_VERSION 20.3.0
ENV JDK_VERSION java11
ENV GRAAL_FILENAME graalvm-ce-${JDK_VERSION}-linux-amd64-${GRAAL_VERSION}.tar.gz

RUN curl -4 -L https://github.com/graalvm/graalvm-ce-builds/releases/download/vm-${GRAAL_VERSION}/${GRAAL_FILENAME} -o /tmp/${GRAAL_FILENAME}
RUN tar -zxvf /tmp/${GRAAL_FILENAME} -C /tmp
RUN mv /tmp/graalvm-ce-${JDK_VERSION}-${GRAAL_VERSION} /usr/lib/graalvm

RUN rm -rf /tmp/*
CMD ["/usr/lib/graalvm/bin/native-image"]

FROM graalvm
COPY --from=builder /home/application/ /home/application/
WORKDIR /home/application
RUN /usr/lib/graalvm/bin/gu install native-image
RUN /usr/lib/graalvm/bin/native-image --no-fallback -cp build/libs/lambdas-*-all.jar --report-unsupported-elements-at-runtime
RUN chmod 755 bootstrap
RUN chmod 755 server
RUN zip -j function.zip bootstrap server
EXPOSE 8080
ENTRYPOINT ["/home/application/server"]
