FROM node:22-alpine

ENV TZ=Asia/Kolkata

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Railway environment variables will be available during build.
# Do NOT hardcode NEXT_PUBLIC_API_URL here.

# Build Next.js app
RUN npm run build

EXPOSE 3000

# Railway provides PORT automatically.
CMD ["sh", "/app/start.sh"]