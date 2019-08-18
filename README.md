# Netbox Deployment on PaaS using Heroku

This repository represents a deployment of Netbox using a PaaS solution.

[Netbox](https://github.com/netbox-community/netbox) is an open source web application designed to help manage and document computer networks.

## Setup

Setup a Heroku account, create a new app, and select the [PostgreSQL](https://www.heroku.com/postgres) and [Redis](https://elements.heroku.com/addons/heroku-redis) add-ons

Clone this repo

```bash
$ git clone https://github.com/mtbutler07/netbox-heroku.git
```

Modify the [.sample.env](./.sample.env) file and rename to it .env

```bash
$ mv .sample.env .env
$ vi .sample.env
```

## Usage

Use the provided [setup script](./setup.sh) to clone Netbox v2.6.2, extract/clean up directories, add optional dependencies, and move configuration/settings files to the proper directory, and generate the static files.

```bash
$ chmod +x ./setup.sh
$ ./setup.sh
```

Use the Python 3 package manager [pip](https://pip.pypa.io/en/stable/) to install the requirements.

```bash
$ python3 -m pip install -r requirements.txt -U --user
```

Deploy to Heroku

```bash
$ git push heroku master
```

## Credits
Initial inspiration for this PoC came from [Sorah's](https://github.com/sorah/heroku-netbox) repo.