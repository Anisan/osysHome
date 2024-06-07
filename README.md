# osysHome 

Object system smarthome

## Install

* git clone https://github.com/Anisan/osysHome.git
* cd osysHome
* python3 -m venv venv
* source venv\bin\activate
* pip install -r requirements.txt
* mkdir plugins

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

* git pull https://github.com/Anisan/osysHome.git
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

## Install recommended modules

* git clone https://github.com/Anisan/osysHome-Modules.git plugins/Modules
* git clone https://github.com/Anisan/osysHome-Objects.git plugins/Objects
* git clone https://github.com/Anisan/osysHome-Users.git plugins/Users
* git clone https://github.com/Anisan/osysHome-Scheduler.git plugins/Scheduler
* git clone https://github.com/Anisan/osysHome-wsServer.git plugins/wsServer
* git clone https://github.com/Anisan/osysHome-Dashboard.git plugins/Dashboard
* git clone https://github.com/Anisan/osysHome-Mqtt.git plugins/Mqtt

## Create docs

pdoc --docformat google --no-show-source --output-dir docs settings.py app plugins

## Systemd

Use osyshome.service

## Docker

* sudo docker build -t osyshome .
* sudo docker run -d --network host -p 5000:5000 osyshome
