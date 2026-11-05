// Declarative pipeline. Portable: no host-specific paths, no hardcoded IPs.
// Application secrets live in the Jenkins secret-file credential `visitor-log-env`
// (content = the .env file: AUTH_USERNAME, AUTH_SALT, AUTH_PASSWORD_HASH, FRONTEND_PORT).
pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        IMAGE_NAME    = 'visitor-log-backend'
        FRONTEND_PORT = '8090'
    }

    triggers {
        // Requires the GitHub plugin and "GitHub hook trigger for GITScm polling"
        // enabled on the job; the webhook URL is the public (ngrok) Jenkins URL.
        githubPush()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Syntax Check') {
            steps {
                sh '''
                    set -eu
                    docker run --rm -v "$WORKSPACE":/src -w /src python:3.11-slim \
                        sh -c 'python -m py_compile backend/app.py setup_account.py && python -m unittest discover -s tests -v'
                '''
            }
        }

        stage('Build Image') {
            steps {
                sh '''
                    set -eu
                    TAG="$(git rev-parse --short=12 HEAD)"
                    echo "$TAG" > .image-tag
                    docker build -t "$IMAGE_NAME:$TAG" -t "$IMAGE_NAME:latest" backend
                    docker image inspect "$IMAGE_NAME:$TAG" --format '{{.Id}}'
                    echo "Built $IMAGE_NAME:$TAG"
                '''
            }
        }

        stage('Automated Deployment') {
            steps {
                withCredentials([file(credentialsId: 'visitor-log-env', variable: 'APP_ENV_FILE')]) {
                    sh '''
                        set -eu
                        TAG="$(cat .image-tag)"
                        IMAGE_TAG="$TAG" docker compose \
                            --env-file "$APP_ENV_FILE" \
                            up -d --no-build --remove-orphans
                        docker compose --env-file "$APP_ENV_FILE" ps
                        echo "Deployed $IMAGE_NAME:$TAG"
                    '''
                }
            }
        }

        stage('Health Check') {
            steps {
                withCredentials([file(credentialsId: 'visitor-log-env', variable: 'APP_ENV_FILE')]) {
                    sh '''
                        set -eu
                        for attempt in $(seq 1 20); do
                            if docker compose --env-file "$APP_ENV_FILE" exec -T frontend \
                                wget -qO- http://127.0.0.1/api/health | grep -q '"status": "ok"'; then
                                echo "Health check passed on attempt $attempt"
                                exit 0
                            fi
                            sleep 3
                        done
                        echo "Health check failed; recent logs:"
                        docker compose --env-file "$APP_ENV_FILE" logs --tail=50
                        exit 1
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "Deployed ${env.IMAGE_NAME} — health check passed"
        }
        failure {
            echo 'Pipeline failed — inspect the failing stage above; do not reset stored data.'
        }
    }
}
