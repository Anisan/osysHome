# osysHome 

Object system smarthome

## Install

* git clone
* python -m venv venv
* source venv\bin\activate
* pip install -r requirement/requirement.txt

## Settings

* Copy settings_sample.py to settings.py
* Change settings db in settings.py

## Mirgrate DB

* flask --app main.py db init
* flask --app main.py db migrate
* flask --app main.py db upgrade

## Start

python3 main.py

## Update

* git pull
* flask --app main.py db migrate
* flask --app main.py db upgrade
* Restart osysHome

## Install module

* Open directory plugins
* Create directory module
* Copy module in directory module
* flask --app main.py db migrate
* flask --app main.py db upgrade
* Restart osysHome

## Update module

* Copy module in directory module
* flask --app main.py db migrate
* flask --app main.py db upgrade
* Restart osysHome

## Create docs

pdoc --docformat google --no-show-source --output-dir docs settings.py app plugins

## Systemd

Use osyshome.service

## Docker

* sudo docker build -t osyshome .
* sudo docker run -d --network host -p 5000:5000 osyshome
