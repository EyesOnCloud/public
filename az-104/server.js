const http = require('http');
const port = process.env.PORT || 8080;


http.createServer((req, res) => {
  const env = process.env.APP_ENVIRONMENT || 'not set';
  const msg = process.env.WELCOME_MESSAGE || 'not set';
  const id = process.env.WEBSITE_INSTANCE_ID || 'local';
  const proto = req.headers['x-forwarded-proto'] || 'http';


  res.writeHead(200, {'Content-Type': 'text/plain'});
  res.end('Contoso Employee Portal\n' +
    'Environment: ' + env + '\n' +
    'Message: ' + msg + '\n' +
    'Instance: ' + id.substring(0, 8) + '\n' +
    'Client protocol: ' + proto + '\n');
}).listen(port);
