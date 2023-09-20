# Website

This website is built using [Docusaurus 2](https://docusaurus.io/), a modern static website generator.

## Installation

```sh
yarn
```

## Local Development

```sh
yarn start
```

This command starts a local development server and opens up a browser window.
Most changes are reflected live without having to restart the server.

## Build

```sh
yarn build
```

This command generates static content in the `build` directory.
It can then be served using any static content hosting service.

## Deployment

Using SSH:

```sh
USE_SSH=true yarn deploy
```

Not using SSH:

```sh
GIT_USER=<Your GitHub username> yarn deploy
```

If you're using GitHub pages, this command is a convenient way to build and push to the `gh-pages` branch.
