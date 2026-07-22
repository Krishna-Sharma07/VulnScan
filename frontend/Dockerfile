FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# --host 0.0.0.0 makes Vite's dev server listen on all interfaces inside the
# container, not just its own localhost - without it, the port mapping in
# docker-compose.yml would have nothing to forward to (see NOTES.md).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
