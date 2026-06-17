pipeline {
    agent { label 'oss-mcp' }

    parameters {
        string(name: 'DOCKER_REGISTRY', defaultValue: '', description: 'Docker registry URL (e.g., registry.example.com/s390x-mcp). Leave empty to skip push.')
        string(name: 'GIT_CREDENTIALS_ID', defaultValue: 'loz-ai-lab-github-app-jenkins', description: 'Jenkins credentials ID for git push')
        string(name: 'DOCKER_CREDENTIALS_ID', defaultValue: 'docker-credentials', description: 'Jenkins credentials ID for Docker registry')
        // Uncomment and set a cron expression to enable scheduled builds:
        // string(name: 'CRON_SCHEDULE', defaultValue: 'H 2 * * 0', description: 'Cron schedule (default: weekly Sunday ~2am)')
    }

    // Uncomment to enable scheduled triggers:
    // triggers {
    //     cron(params.CRON_SCHEDULE ?: 'H 2 * * 0')
    // }

    environment {
        WIKI_DIR     = "${WORKSPACE}/upstream/wiki"
        SCRIPTS_DIR  = "${WORKSPACE}/upstream/scripts"
        WIKI_URL     = 'https://github.com/linux-on-ibm-z/docs.wiki.git'
        SCRIPTS_URL  = 'https://github.com/linux-on-ibm-z/scripts.git'
        VENV_DIR     = "${WORKSPACE}/.venv"
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Clone Sources') {
            steps {
                sh '''
                    mkdir -p upstream
                    git clone --depth 1 "$WIKI_URL" "$WIKI_DIR"
                    git clone --depth 1 "$SCRIPTS_URL" "$SCRIPTS_DIR"
                '''
            }
        }

        stage('Check for Changes') {
            steps {
                script {
                    def wikiSha = sh(script: "git -C \"$WIKI_DIR\" rev-parse HEAD", returnStdout: true).trim()
                    def scriptsSha = sh(script: "git -C \"$SCRIPTS_DIR\" rev-parse HEAD", returnStdout: true).trim()
                    def shasFile = "${WORKSPACE}/.last_upstream_shas"

                    env.WIKI_SHA = wikiSha
                    env.SCRIPTS_SHA = scriptsSha

                    def currentShas = "${wikiSha}\n${scriptsSha}"
                    def previousShas = ''

                    // Compare against last successful build
                    if (currentBuild.previousSuccessfulBuild) {
                        try {
                            previousShas = currentBuild.previousSuccessfulBuild.description ?: ''
                        } catch (e) {
                            previousShas = ''
                        }
                    }

                    if (previousShas == currentShas) {
                        echo "Upstream sources unchanged (wiki: ${wikiSha}, scripts: ${scriptsSha}). Skipping rebuild."
                        currentBuild.result = 'NOT_BUILT'
                        env.SKIP_REBUILD = 'true'
                    } else {
                        echo "Changes detected. wiki: ${wikiSha}, scripts: ${scriptsSha}"
                        env.SKIP_REBUILD = 'false'
                    }
                }
            }
        }

        stage('Setup Python') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh '''
                    python3 -m venv "$VENV_DIR"
                    . "$VENV_DIR/bin/activate"
                    pip install --upgrade pip
                    pip install -e .
                    pip install -r mcp-server/requirements.txt
                    pip install pytest
                '''
            }
        }

        stage('Generate Chunks') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh '''
                    . "$VENV_DIR/bin/activate"
                    python3 embedding-generation/generate_chunks.py \
                        --wiki-dir "$WIKI_DIR" \
                        --scripts-dir "$SCRIPTS_DIR" \
                        --output-dir embedding-generation/output \
                        --script-index-output mcp-server/data/script_index.json
                '''
            }
        }

        stage('Generate Vector Index') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh '''
                    . "$VENV_DIR/bin/activate"
                    python3 embedding-generation/local_vectorstore_creation.py \
                        --metadata embedding-generation/output/metadata.json \
                        --output-dir mcp-server/data
                '''
            }
        }

        stage('Evaluate Quality') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh '''
                    . "$VENV_DIR/bin/activate"
                    bash embedding-generation/run_eval.sh | tee eval_output.txt

                    HIT1=$(sed -n 's/.*Hit@1: \\([0-9.]*\\).*/\\1/p' eval_output.txt)
                    HIT3=$(sed -n 's/.*Hit@3: \\([0-9.]*\\).*/\\1/p' eval_output.txt)
                    MRR=$(sed -n 's/.*MRR: *\\([0-9.]*\\).*/\\1/p' eval_output.txt)

                    python3 -c "
import sys
h1, h3, mrr = float('${HIT1}'), float('${HIT3}'), float('${MRR}')
failed = []
if h1 < 0.60: failed.append(f'Hit@1 {h1:.4f} < 0.60')
if h3 < 0.80: failed.append(f'Hit@3 {h3:.4f} < 0.80')
if mrr < 0.70: failed.append(f'MRR {mrr:.4f} < 0.70')
if failed:
    print('Quality gate FAILED: ' + ', '.join(failed))
    sys.exit(1)
print('Quality gate passed.')
"
                '''
            }
        }

        stage('Run Tests') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh '''
                    . "$VENV_DIR/bin/activate"
                    python3 -m pytest mcp-server/tests/ -v
                '''
            }
        }

        stage('Commit Data') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                script {
                    def hasChanges = sh(
                        script: 'git diff --quiet mcp-server/data/ || echo changed',
                        returnStdout: true
                    ).trim()

                    if (hasChanges == 'changed') {
                        withCredentials([usernamePassword(
                            credentialsId: params.GIT_CREDENTIALS_ID,
                            usernameVariable: 'GIT_USER',
                            passwordVariable: 'GIT_TOKEN'
                        )]) {
                            sh '''
                                git config user.name "Jenkins CI"
                                git config user.email "jenkins@ci.local"
                                git add mcp-server/data/metadata.json mcp-server/data/usearch_index.bin mcp-server/data/script_index.json
                                git commit -m "Update knowledge base from upstream sources

wiki: ${WIKI_SHA}
scripts: ${SCRIPTS_SHA}"
                                git push https://${GIT_USER}:${GIT_TOKEN}@$(git remote get-url origin | sed 's|https://||') HEAD:main
                            '''
                        }
                    } else {
                        echo 'Data files unchanged after regeneration. Skipping commit.'
                    }
                }
            }
        }

        stage('Docker Build & Push') {
            when { expression { env.SKIP_REBUILD != 'true' } }
            steps {
                sh 'docker build -t s390x-mcp:embeddings-latest -f embedding-generation/Dockerfile .'
                sh 'docker build -t s390x-mcp:latest -f mcp-server/Dockerfile .'

                script {
                    if (params.DOCKER_REGISTRY) {
                        def tag = "${params.DOCKER_REGISTRY}:latest"
                        withCredentials([usernamePassword(
                            credentialsId: params.DOCKER_CREDENTIALS_ID,
                            usernameVariable: 'DOCKER_USER',
                            passwordVariable: 'DOCKER_PASS'
                        )]) {
                            sh """
                                echo "\$DOCKER_PASS" | docker login -u "\$DOCKER_USER" --password-stdin ${params.DOCKER_REGISTRY.split('/')[0]}
                                docker tag s390x-mcp:latest ${tag}
                                docker push ${tag}
                            """
                        }
                    } else {
                        echo 'No DOCKER_REGISTRY set. Skipping push.'
                    }
                }
            }
        }
    }

    post {
        success {
            script {
                if (env.SKIP_REBUILD != 'true') {
                    currentBuild.description = "${env.WIKI_SHA}\n${env.SCRIPTS_SHA}"
                }
            }
        }
        always {
            cleanWs(deleteDirs: true, patterns: [[pattern: 'upstream/**', type: 'INCLUDE']])
        }
    }
}
