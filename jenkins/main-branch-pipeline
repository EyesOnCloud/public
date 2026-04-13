pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo "=== Main Branch Build ==="
                echo "Branch : ${GIT_BRANCH}"
                echo "Commit : ${GIT_COMMIT}"
            }
        }

        stage('Build') {
            steps {
                echo "Building main branch..."
                sh 'ls -la'
                sh 'mkdir -p build && echo "main-build" > build/output.txt'
                echo "Build complete"
            }
        }

        stage('Test') {
            steps {
                echo "Running full test suite on main..."
                sh 'test -f build/output.txt && echo "Build output found - OK"'
                sh 'test -f index.html && echo "index.html found - OK"'
                echo "All tests passed"
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                echo "=== Deploying to Staging ==="
                echo "Branch ${GIT_BRANCH} is main - deploying"
                echo "Staging deployment complete"
            }
        }

    }

    post {
        always {
            sh 'rm -rf build/'
            echo "Cleanup done"
        }
        success {
            echo "Main branch build PASSED - artifact deployed to staging"
        }
        failure {
            echo "Main branch build FAILED"
        }
    }
}
