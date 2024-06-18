"""Login form"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField("Username", id="username_login", validators=[DataRequired()])
    password = PasswordField("Password", id="pwd_login", validators=[DataRequired()])
