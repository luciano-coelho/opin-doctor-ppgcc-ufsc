# Vendored dependency: insurance-swagger 1.2.0.2

`com.raidiam.trustframework.mockinsurance:insurance-swagger:1.2.0.2` is a
Raidiam-internal artifact, never published to Maven Central or any public
repository. Without it vendored here, a clean build container (no host
`~/.m2` cache, such as a third party's machine or this project's own Docker
build) cannot resolve this dependency and `gradle build` fails.

Redistribution of this jar is authorized (informed by the thesis author; see
`thesis/results/v9/DECISIONS.md`). This directory is a local Maven-repository
layout (jar + POM + Gradle module metadata, copied verbatim from the
original artifact) consumed by `insurance-server-lambdas/build.gradle` via:

```groovy
maven { url "file://${projectDir}/vendor/maven-repo" }
```

## Rebuilding the mockapi image from scratch

A third party with only this repository (no access to Raidiam's internal
Maven repository, no pre-populated `~/.m2`) reproduces the image with:

```sh
cd insurance-server-lambdas
docker build --no-cache -t raidiam-insurance-lambdas:latest .
```

The vendored jar under `vendor/maven-repo/` is all `gradle build` needs for
this one dependency; every other dependency resolves normally from Maven
Central.
