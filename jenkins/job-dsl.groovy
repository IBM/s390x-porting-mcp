// Job DSL script for s390x MCP knowledge base update pipeline.
//
// Usage:
//   1. Create a "Seed Job" in Jenkins (Freestyle project)
//   2. Add a "Process Job DSLs" build step
//   3. Point it at this file (or paste the contents inline)
//   4. Run the seed job — it creates the "s390x-mcp-kb-update" pipeline job
//
// Prerequisites:
//   - Jenkins plugins: Pipeline, Job DSL, Git, Credentials Binding, Timestamps
//   - A credential in Jenkins for github.ibm.com access (SSH key or username/token)
//   - Python 3.10+, Docker, and Git available on the build agent
//
// To customize:
//   - Change REPO_URL to your fork/mirror
//   - Change CREDENTIALS_ID to match your Jenkins credential
//   - Uncomment the cron trigger for scheduled builds
//   - Set DOCKER_REGISTRY default to your internal registry

def REPO_URL        = 'git@github.ibm.com:loz-ai-lab/s390x-mcp.git'
def CREDENTIALS_ID  = 'github-ibm-ssh'   // Change to your Jenkins credential ID
def BRANCH          = 'main'

pipelineJob('s390x-mcp-kb-update') {
    description('Periodic knowledge base update for the s390x MCP server. ' +
                'Clones upstream wiki/scripts, regenerates embeddings, ' +
                'validates quality, runs tests, commits data, and builds Docker image.')

    properties {
        disableConcurrentBuilds()
    }

    parameters {
        stringParam('DOCKER_REGISTRY', '',
                    'Docker registry URL (e.g., registry.example.com/s390x-mcp). Leave empty to skip push.')
        stringParam('GIT_CREDENTIALS_ID', CREDENTIALS_ID,
                    'Jenkins credentials ID for git push')
        stringParam('DOCKER_CREDENTIALS_ID', 'docker-credentials',
                    'Jenkins credentials ID for Docker registry')
    }

    // Uncomment ONE of these trigger blocks when ready:
    //
    // Weekly (Sunday ~2am):
    // triggers { cron('H 2 * * 0') }
    //
    // Daily (~2am):
    // triggers { cron('H 2 * * *') }

    definition {
        cpsScm {
            scm {
                git {
                    remote {
                        url(REPO_URL)
                        credentials(CREDENTIALS_ID)
                    }
                    branches("*/${BRANCH}")
                }
            }
            scriptPath('Jenkinsfile')
        }
    }

    logRotator {
        numToKeep(20)
        artifactNumToKeep(5)
    }
}
