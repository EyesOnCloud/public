CONFIG_FILE=/opt/kafka/config/server-broker2.properties

sed -i 's/^node.id=.*/node.id=2/' "$CONFIG_FILE"

sed -i 's|^listeners=.*|listeners=PLAINTEXT://:9094,CONTROLLER://:9095|' "$CONFIG_FILE"

sed -i 's|^advertised.listeners=.*|advertised.listeners=PLAINTEXT://localhost:9094|' "$CONFIG_FILE"

sed -i 's|^controller.quorum.voters=.*|controller.quorum.voters=1@localhost:9093,2@localhost:9095,3@localhost:9097|' "$CONFIG_FILE"

sed -i 's|^log.dirs=.*|log.dirs=/opt/kafka/data-broker2|' "$CONFIG_FILE"
