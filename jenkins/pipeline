pipeline {
    agent any

    environment {
        APP_NAME = 'lab14-app'
        VERSION  = "1.0.${BUILD_NUMBER}"
    }

    stages {

        stage('Checkout') {
            steps {
                echo "Starting build for ${APP_NAME} version ${VERSION}"
                echo "Build URL: ${BUILD_URL}"
            }
        }

        stage('Build') {
            steps {
                echo "Building ${APP_NAME}..."
                sh 'mkdir -p build'
                sh 'echo "Build artifact for version ${VERSION}" > build/app.txt'
                echo "Build complete"
            }
        }

        stage('Test') {
            steps {
                echo "Running tests for ${APP_NAME}..."
                sh 'test -f build/app.txt && echo "Artifact exists - OK"'
                echo "Tests passed"
            }
        }

        stage('Package') {
            steps {
                echo "Packaging version ${VERSION}..."
                sh 'cat build/app.txt'
                echo "Package ready"
            }
        }

    }

    post {
        success {
            echo "Pipeline PASSED - ${APP_NAME} version ${VERSION} is ready"
        }
        failure {
            echo "Pipeline FAILED - check the logs above for details"
        }
        always {
            echo "Pipeline finished with status: ${currentBuild.result}"
        }
    }
}
