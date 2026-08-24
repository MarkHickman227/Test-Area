FROM node:22-alpine AS deps
WORKDIR /web
COPY apps/web/package.json /web/package.json
RUN npm install

FROM node:22-alpine AS build
WORKDIR /web
COPY --from=deps /web/node_modules /web/node_modules
COPY apps/web /web
ARG API_BASE_URL=http://api:8000
ENV API_BASE_URL=$API_BASE_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web/.next/standalone /web
COPY --from=build /web/.next/static /web/.next/static
COPY --from=build /web/public /web/public
EXPOSE 3000
CMD ["node", "server.js"]
