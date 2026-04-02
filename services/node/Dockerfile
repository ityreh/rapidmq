FROM node:20-slim

WORKDIR /app

COPY package.json /app/package.json

RUN npm install --production

COPY index.js /app/index.js

EXPOSE 8083

CMD ["node", "index.js"]
