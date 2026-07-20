.PHONY: setup setup-cs run run-with-cs rebuild

setup:
	cd insurance-swagger; BUILD_NUMBER=2 ./gradlew publishToMavenLocal

run:
	cd insurance-server-lambdas; ./gradlew optimizedDockerBuild -x test
	cd insurance-server-lambdas; docker-compose --profile main up

setup-cs:
	# git clone --branch main --single-branch --depth=1 https://gitlab.com/raidiam-conformance/open-insurance/open-insurance-brasil.git insurance-server-lambdas/conformance-suite
	# mkdir -p insurance-server-lambdas/conformance-suite/server-dev
	# echo 'FROM openjdk:17-jdk-slim\n\nRUN apt-get update && apt-get install redir' > insurance-server-lambdas/conformance-suite/server-dev/Dockerfile
	cd insurance-server-lambdas; docker-compose run cs-builder

run-with-cs:
	cd insurance-server-lambdas; ./gradlew optimizedDockerBuild -x test
	cd insurance-server-lambdas; docker-compose --profile main --profile cs up

rebuild:
	cd insurance-swagger; BUILD_NUMBER=2 ./gradlew publishToMavenLocal
	cd insurance-server-lambdas; docker-compose build auth
	cd insurance-server-lambdas; docker-compose build mtls
