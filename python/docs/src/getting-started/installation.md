# Installation

The repo is private, so the installation process is a bit more involved than usual.

## Option 1: Install from GitHub

To install the package from GitHub, you will need to authenticate with GitHub.

```sh
GITHUB_TOKEN=$(gh auth token)
pip install git+https://oauth2:$GITHUB_TOKEN@github.com/microsoft/agnext.git
```

### Using a Personal Access Token instead of `gh` CLI

If you don't have the `gh` CLI installed, you can generate a personal access token from the GitHub website.

1. Go to [New fine-grained personal access token](https://github.com/settings/personal-access-tokens/new)
2. Set `Resource Owner` to `Microsoft`
3. Set `Repository Access` to `Only select repositories` and select `Microsoft/agnext`
4. Set `Permissions` to `Repository permissions` and select `Contents: Read`
5. Use the generated token for `GITHUB_TOKEN` in the commad above

## Option 2: Install from a local copy

With a copy of the repo cloned locally, you can install the package by running the following command from the root of the repo:

```sh
pip install .
```
