const http = require('http');
const VERSION = 'v1.0';
const port = process.env.PORT || 8080;


http.createServer((req, res) => {
  const e = process.env;


  res.writeHead(200, {'Content-Type': 'text/plain'});
  res.end('Contoso Order Tracking\n' +
    'Version: ' + VERSION + '\n' +
    'Environment: ' + (e.APP_ENVIRONMENT || 'not set') + '\n' +
    'Database: ' + (e.DB_SERVER || 'not set') + '\n' +
    'New checkout: ' + (e.FEATURE_NEW_CHECKOUT || 'not set') + '\n');
}).listen(port);
