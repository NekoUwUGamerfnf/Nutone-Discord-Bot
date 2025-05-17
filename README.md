`docker pull ghcr.io/nekouwugamerfnf/nutone-api-discord-bot:latest`

`x-logging:
  &logging
  logging:
    driver: "json-file"
    options:
      max-file: "5"
      max-size: "400m"

services:
  Nutone-Bot:
    << : *logging
    image: ghcr.io/nekouwugamerfnf/nutone-api-discord-bot:latest
    pull_policy: always
    restart: always
`