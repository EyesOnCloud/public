pipeline {
    agent any

    environment {
        BRANCH_NAME_CLEAN = "${GIT_BRANCH}".replaceAll('origin/', '')
    }

    stages {

        stage('Checkout') {
            steps {
                echo "=== Feature Branch Build ==="
                echo "Branch : ${GIT_BRANCH}"
                echo "Commit : ${GIT_COMMIT}"
            }
        }

        stage('Build') {
            steps {
                echo "Building feature branch..."
                sh 'ls -la'
                sh 'mkdir -p build && echo "feature-build" > build/output.txt'
                echo "Build complete"
            }
        }

        stage('Test') {
            steps {
                echo "Running tests on feature branch..."
                sh 'test -f build/output.txt && echo "Build output found - OK"'
                echo "Feature branch tests passed"
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo "Deploying to staging..."
                echo "This stage only runs on main branch"
            }
        }

    }

    post {
        always {
            sh 'rm -rf build/'
            echo "Cleanup done on ${GIT_BRANCH}"
        }
        success {
            echo "Feature branch build PASSED: ${GIT_BRANCH}"
        }
        failure {
            echo "Feature branch build FAILED: ${GIT_BRANCH}"
        }
    }
}
