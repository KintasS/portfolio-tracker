from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from flask_login import current_user
from wtforms import (StringField, PasswordField, SubmitField, BooleanField,
                     TextAreaField, DateTimeField, FloatField, SelectField)
from wtforms.validators import (DataRequired, Length, Email, EqualTo,
                                ValidationError, Optional)
from portfolio_tracker.models import User
from portfolio_tracker.config import Params
from portfolio_tracker.utils import get_type_choices, get_allowed_currencies


class RegistrationForm(FlaskForm):
    username = StringField('Usuario',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar contraseña',
                                     validators=[DataRequired(),
                                                 EqualTo('password')])
    currency = SelectField('Divisa de cálculo',
                           choices=get_allowed_currencies(),
                           validators=[DataRequired(), Length(max=10)])
    submit = SubmitField('Registrarse')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("Usuario ya registrado. "
                                  "Por favor, elija uno diferente.")

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("Email ya registrado. "
                                  "Por favor, elija uno diferente.")


class LoginForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember = BooleanField('Recordarme')
    submit = SubmitField('Acceder')


class UpdateAccountForm(FlaskForm):
    username = StringField('Usuario',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    currency = SelectField('Divisa de cálculo',
                           choices=get_allowed_currencies(),
                           validators=[DataRequired(), Length(max=10)])
    picture = FileField('Imagen de perfil',
                        validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Actualizar')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError("Usuario ya registrado. "
                                      "Por favor, elija uno diferente.")

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError("Email ya registrado. "
                                      "Por favor, elija uno diferente.")

    def validate_currency(self, currency):
        if currency.data != current_user.currency:
            if currency.data not in Params.CURRENCIES:
                raise ValidationError("That cryptocurrency is not currenty "
                                      "supported by the sistem. Chose among "
                                      "the following: '{}'"
                                      .format(Params.CURRENCIES))


class ImportOperationsForm(FlaskForm):
    file = FileField('Fichero a importar',
                     validators=[FileRequired(),
                                 FileAllowed(['csv'],
                                             "Solo se admiten archivos CSV")])
    submit = SubmitField('Ok, vamos allá!')


class EditOperationForm(FlaskForm):

    date = DateTimeField('Fecha',
                         format="%Y-%m-%d",
                         validators=[DataRequired()])
    exchange = StringField('Exchange', validators=[DataRequired(),
                                                   Length(max=20)])
    type = SelectField('Tipo',
                       choices=get_type_choices(),
                       validators=[DataRequired(), Length(max=10)])
    buy_amount = FloatField('Cantidad',
                            validators=[Optional()],
                            filters=[lambda x: x or None])
    buy_coin = StringField('Moneda',
                           validators=[Length(max=10)],
                           filters=[lambda x: x or None])
    sell_amount = FloatField('Cantidad',
                             validators=[Optional()],
                             filters=[lambda x: x or None])
    sell_coin = StringField(' Moneda',
                            validators=[Length(max=10)],
                            filters=[lambda x: x or None])
    fee_amount = FloatField('Cantidad',
                            validators=[Optional()],
                            filters=[lambda x: x or None])
    fee_coin = StringField('Moneda',
                           validators=[Length(max=10)],
                           filters=[lambda x: x or None])
    comment = TextAreaField('Comentario',
                            validators=[Length(max=200)],
                            filters=[lambda x: x or None])
    submit = SubmitField('Guardar')

    def validate_type(self, type):
        if type.data not in Params.OPERATION_TYPES:
            raise ValidationError("Tipo de operación no reconocido. Elija "
                                  "entre: '{}'".format(Params.OPERATION_TYPES))

    # def validate_buy_amount(self, buy_amount):
    #     if self.type.data in ['Expense', 'Withdrawal']:
    #         if buy_amount.data:
    #             raise ValidationError("Este campo debe estar vacío para "
    #                                   "este tipo de operación")
    #     else:
    #         if not buy_amount.data:
    #             raise buy_amountValidationError("Este campo NO debe estar "
    #                                   "vacío para este tipo de operación")

    def validate_buy_coin(self, buy_coin):
        if self.type.data in ['Expense', 'Withdrawal']:
            if buy_coin.data:
                raise ValidationError("Estos campos deben estar vacíos "
                                      "para este tipo de operación")
        else:
            if not buy_coin.data:
                raise ValidationError("Estos campos NO deben estar vacíos "
                                      "para este tipo de operación")

    # def validate_sell_amount(self, sell_amount):
    #     if self.type.data in ['Airdrop', 'Deposit', 'Fork', 'Income']:
    #         if sell_amount.data:
    #             raise ValidationError("Este campo debe estar vacío para "
    #                                   "este tipo de operación")
    #     else:
    #         if not sell_amount.data:
    #             raise ValidationError("Este campo NO debe estar vacío para "
    #                                   "este tipo de operación")

    def validate_sell_coin(self, sell_coin):
        if self.type.data in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if sell_coin.data:
                raise ValidationError("Estos campos deben estar vacíos "
                                      "para este tipo de operación")
        else:
            if not sell_coin.data:
                raise ValidationError("Estos campos NO deben estar vacíos "
                                      "para este tipo de operación")

    # def validate_fee_amount(self, fee_amount):
    #     if self.type.data in ['Airdrop', 'Deposit', 'Fork', 'Income']:
    #         if fee_amount.data:
    #             raise ValidationError("Este campo debe estar vacío para "
    #                                   "este tipo de operación")
    #     else:
    #         if not fee_amount.data:
    #             raise ValidationError("Este campo NO debe estar vacío para "
    #                                   "este tipo de operación")

    def validate_fee_coin(self, fee_coin):
        if self.type.data in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if fee_coin.data:
                raise ValidationError("Estos campos deben estar vacíos "
                                      "para este tipo de operación")
        else:
            if not fee_coin.data:
                raise ValidationError("Estos campos NO deben estar vacíos "
                                      "para este tipo de operación")


class RequestResetForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    submit = SubmitField('Solicitar reseteo de contraseña')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError("No existe cuenta asociada a ese correo.")


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar contraseña',
                                     validators=[DataRequired(),
                                                 EqualTo('password')])
    submit = SubmitField('Guardar')
