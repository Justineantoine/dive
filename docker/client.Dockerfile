# ========================
# == CLIENT BUILD STAGE ==
# ========================
FROM node:18
WORKDIR /app

# Install dependencies
COPY client/package.json client/yarn.lock /app/
RUN yarn install --frozen-lockfile --network-timeout 300000
# Build
COPY .git/ /app/.git/
COPY client/ /app/
COPY docker/entrypoint_client.sh /
ENTRYPOINT [ "/entrypoint_client.sh" ]