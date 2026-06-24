CONFIG_FILE=/opt/kafka/config/server-broker3.properties

sed -i 's/^node.id=.*/node.id=3/' "$CONFIG_FILE"

sed -i 's|^listeners=.*|listeners=PLAINTEXT://:9096,CONTROLLER://:9097|' "$CONFIG_FILE"

sed -i 's|^advertised.listeners=.*|advertised.listeners=PLAINTEXT://localhost:9096|' "$CONFIG_FILE"

echo 'controller.quorum.voters=1@localhost:9093,2@localhost:9095,3@localhost:9097' >> "$CONFIG_FILE"

sed -i 's|^log.dirs=.*|log.dirs=/opt/kafka/data-broker3|' "$CONFIG_FILE"
