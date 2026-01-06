FROM ubuntu:24.04
RUN apt-get update && apt-get install -y nginx
RUN rm -f /usr/share/nginx/html/*
COPY index.html /usr/share/nginx/html/
RUN sed -i 's|root /var/www/html;|root /usr/share/nginx/html;|g' /etc/nginx/sites-enabled/default
EXPOSE 80/tcp
CMD ["nginx", "-g", "daemon off;"]
