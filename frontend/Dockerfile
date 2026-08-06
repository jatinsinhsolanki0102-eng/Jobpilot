FROM node:22-alpine

ENV TZ=Asia/Kolkata

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Railway injects service variables during the build, but Docker only exposes
# them to `next build` if declared as ARG here. NEXT_PUBLIC_* vars are inlined
# into the client bundle at build time.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build Next.js app
RUN npm run build

EXPOSE 3000

# Railway provides PORT automatically.
CMD ["sh", "/app/start.sh"]