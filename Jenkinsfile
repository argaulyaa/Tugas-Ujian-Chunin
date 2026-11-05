// VM-specific pipeline; application secrets remain in the private host .env.
pipeline {
 agent any
 options { disableConcurrentBuilds(); skipDefaultCheckout(true); timeout(time:15, unit:'MINUTES') }
 stages {
  stage('Checkout') { steps { checkout scm } }
  stage('Test') { steps { sh '''docker run --rm --volumes-from visitor-log-jenkins -w "$WORKSPACE" python:3.12-slim python -m unittest discover -s tests -v''' } }
  stage('Build') { steps { sh 'docker build -t visitor-log-backend:deploy backend' } }
  stage('Deploy') { steps {
   sh '''set -eu
    docker run --rm --volumes-from visitor-log-jenkins -v /home/ubuntu/cloud-computing:/home/ubuntu/cloud-computing -w "$WORKSPACE" python:3.12-slim python -c 'import pathlib,shutil; src=pathlib.Path("frontend"); dst=pathlib.Path("/home/ubuntu/cloud-computing/visitor-log-app/frontend"); [shutil.copy2(p,dst/p.name) for p in src.iterdir() if p.is_file()]'
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v /home/ubuntu/cloud-computing:/home/ubuntu/cloud-computing -v /usr/bin/docker:/usr/local/bin/docker:ro -v /usr/libexec/docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro python:3.12-slim docker compose -f /home/ubuntu/cloud-computing/compose.deploy.yml --env-file /home/ubuntu/cloud-computing/.env up -d --no-build
   '''
  } }
  stage('Health Check') { steps { sh '''set -eu
   for n in $(seq 1 20); do
    if curl -fsS --max-time 3 http://172.20.100.100:8090/api/health && curl -fsS --max-time 3 -o /dev/null http://172.20.100.100:8090/login.html; then exit 0; fi
    sleep 3
   done
   exit 1
   ''' } }
 }
}
