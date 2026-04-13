pipeline {
    agent any

    environment {
        APP_NAME = 'jenkins-demo'
        VERSION  = "1.0.${BUILD_NUMBER}"
    }

    stages {

        stage('Checkout') {
            steps {
                echo "=== ${APP_NAME} Pipeline ==="
                echo "Branch  : ${GIT_BRANCH}"
                echo "Commit  : ${GIT_COMMIT}"
                echo "Version : ${VERSION}"
            }
        }

        stage('Build') {
            steps {
                echo "Building ${APP_NAME}..."
                sh 'ls -la'
                sh 'mkdir -p build && echo "${APP_NAME}-${VERSION}" > build/app.txt'
                echo "Build complete"
            }
            post {
                success { echo "Build artifact ready" }
                failure { echo "Build failed" }
            }
        }

        stage('Test') {
            steps {
                echo "Running tests..."
                sh 'test -f build/app.txt && echo "Artifact found - OK"'
                sh 'test -f index.html && echo "index.html found - OK"'
                echo "Tests passed"
            }
        }

        stage('Deploy Staging') {
            when {
                branch 'main'
            }
            steps {
                echo "=== Deploy to Staging ==="
                echo "Deploying ${VERSION} to staging..."
                sh 'cat build/app.txt'
                echo "Staging deploy complete"
            }
        }

        stage('Deploy Production') {
            when {
                allOf {
                    branch 'main'
                    expression { return env.BUILD_NUMBER.toInteger() > 3 }
                }
            }
            steps {
                echo "=== Deploy to Production ==="
                echo "Deploying ${VERSION} to production"
                echo "Production deploy complete"
            }
        }

    }

    post {
        always {
            sh 'rm -rf build/'
            echo "Cleanup done"
        }
        success {
            echo "SUCCESS: ${APP_NAME} ${VERSION} on ${GIT_BRANCH}"
        }
        failure {
            echo "FAILURE: ${APP_NAME} ${VERSION} on ${GIT_BRANCH}"
        }
    }
}
