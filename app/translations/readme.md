
$ pybabel extract -F babel.cfg --ignore-dirs=venv -k lazy_gettext -o messages.pot .
This will use the mapping from the babel.cfg file and store the generated template in messages.pot. Now we can create the first translation. For example to translate to German use this command:

$ pybabel init -i messages.pot -d translations -l de
-d translations tells pybabel to store the translations in a directory called “translations”. This is the default folder where Flask-Babel will look for translations unless you changed BABEL_TRANSLATION_DIRECTORIES and should be at the root of your application.

Now edit the translations/de/LC_MESSAGES/messages.po file as needed. Check out some gettext tutorials if you feel lost.

To compile the translations for use, pybabel helps again:

$ pybabel compile -d translations
What if the strings change? Create a new messages.pot like above and then let pybabel merge the changes:

$ pybabel update -i messages.pot -d translations