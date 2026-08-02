FROM node:22-alpine

ENV TZ=Asia/Kolkata

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

EXPOSE 3000

# PORT is set by Railway; falls back to 3000 for docker-compose.
CMD ["sh", "-c", "next start -p ${PORT:-3000}"]
