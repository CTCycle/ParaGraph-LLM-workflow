FROM node:22.12.0-alpine AS build

WORKDIR /app/client

COPY APP/client/package.json APP/client/package-lock.json* ./
RUN npm ci || npm install

COPY APP/client ./
RUN npm run build

FROM nginx:1.27.5-alpine

COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/client/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
