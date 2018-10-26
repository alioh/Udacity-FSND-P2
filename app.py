#!/usr/bin/env python3
#####################################################
#                   Ali Alohali                     #
#                    alioh.com                      #
#                                                   #
#    Udacity Full Stack Web Developer Nanodegree    #
#            Project Two: Item Catalog              #
#              https://goo.gl/BxcjQz                #
#     Read README.md file for more explanation      #
#####################################################


from flask import Flask, g, redirect, url_for, render_template,\
             flash, request, abort, jsonify
from flask_oidc import OpenIDConnect
from okta import UsersClient
from os import environ
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from model import Base, User, Item
#   FlaskWTF/WTForms used to create forms
#   Reference:
# - https://flask-wtf.readthedocs.io/en/stable/
# - https://wtforms.readthedocs.io/en/stable/fields.html
# - https://goo.gl/1sxgiP
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import InputRequired
from flask_bootstrap import Bootstrap


#   Creating the app
app = Flask(__name__)
Bootstrap(app)

#   Database
engine = create_engine('sqlite:///catalog.db?check_same_thread=False')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

#   Default categories
categories = [
            'Football',
            'Basketball',
            'Baseball',
            'Frisbee',
            'Snowboarding',
            'Rock Climbing',
            'Tennis',
            'Hockey'
            ]


#   Okta: I used Okta for authentication and user registration.
#   Reference:
# - https://goo.gl/JfopBQ
# - https://goo.gl/JEG5an

#   Set environment variables, needed to be used for Okta
environ["OKTA_ORG_URL"] = "https://dev-906070.oktapreview.com"
environ["OKTA_AUTH_TOKEN"] = "00OmAGHH00KRCNJiVpnj8GsqIDBK4e8sk2uu-rx4LO"
environ["SECRET_KEY"] = 'notreallyasecret'


#   making the Okta connection
app.config["OIDC_CLIENT_SECRETS"] = "openidconnect_secrets.json"
app.config["OIDC_COOKIE_SECURE"] = False
app.config["OIDC_CALLBACK_ROUTE"] = "/oidc/callback"
app.config["OIDC_SCOPES"] = ["openid", "email", "profile"]
app.config["SECRET_KEY"] = environ.get("SECRET_KEY")
app.config["OIDC_ID_TOKEN_COOKIE_NAME"] = "oidc_token"


#   OpenID Client to handle user session
#   Reference: - https://flask-oidc.readthedocs.io/en/latest/
oidc = OpenIDConnect(app)


#   Okta Client to check if user have account
okta_client = UsersClient(environ.get("OKTA_ORG_URL"),
                          environ.get("OKTA_AUTH_TOKEN"))


#   Check if the user logged in
@app.before_request
def before_request():
    if oidc.user_loggedin:
        g.user = okta_client.get_user(oidc.user_getfield("sub"))
    else:
        g.user = None


#   Index route / Home page
@app.route('/')
@oidc.require_login
def index():
    title = 'Your Catalog'
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    items = session.query(Item).filter_by(user_id=user.id).all()
    return render_template('index.html', items=items,
                           user=user.id, categories=categories, title=title)


#   User can get json of one item
@app.route('/item/<int:item_id>/json', methods=['GET'])
@oidc.require_login
def jsonItem(item_id):
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    item = session.query(Item).filter_by(id=item_id).first()
    return jsonify(item=item.serialize)


#   User can get json file of all their itmes
@app.route('/index/<int:user_id>/json', methods=['GET'])
@oidc.require_login
def jsonAll(user_id):
    items = session.query(Item).filter_by(user_id=user_id).all()
    return jsonify(item=[i.serialize for i in items])


#   Creating Flask Forms
#   Dashboard form
class Dashboard(FlaskForm):
    name = StringField('Name', validators=[InputRequired()])
    email = StringField('Email', render_kw={'readonly': True})


#   Item form
class ItemForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired()])
    description = StringField('Description')
    #   Choices: https://goo.gl/hoYYb8
    category = SelectField('Category', validators=[InputRequired()])


#   login page, will redirect to Okta to login
#   after login, it will store users data in the database and redirect to index
@app.route("/login")
@oidc.require_login
def login():
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    if not user:
        u = User(
            name=oidc.user_getfield('name'),
            email=oidc.user_getfield('email')
        )
        session.add(u)
        session.commit()
        session.close()
    return redirect(url_for('index'))


#   This is a dashboard where the user can change their name
@app.route("/dashboard", methods=['GET', 'POST'])
@oidc.require_login
def dashboard():
    dash_session = DBSession()
    user = dash_session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    form = Dashboard()
    title = title = "{}'s dashboard".format(user.name)
    # try:
    #   populate email in html
    form.email.data = user.email
    #   Do changes if user asked
    if form.validate_on_submit():
        flash('Name was changed to {}'.format(form.name.data))
        user.name = form.name.data
        dash_session.commit()
        dash_session.close()
    form.name.data = user.name
    return render_template('dashboard.html',
                           user=user, form=form, title=title)
    # except:
    #     return render_template('dashboard.html',
    #                             user=user, form=form, title=title)


#   View all items in specific category
@app.route('/category/<string:name>')
@oidc.require_login
def viewCategory(name):
    cat_session = DBSession()
    user = cat_session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    items = cat_session.query(Item).filter_by(
        user_id=user.id, category=name).all()
    return render_template('index.html',
                           items=items, categories=categories,)


#   Add new Item page
@app.route('/add', methods=['GET', 'POST'])
@oidc.require_login
def addItem():
    title = 'Add New Item'
    form = ItemForm()
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    form.category.choices = [(i, i) for i in categories]
    if form.validate_on_submit():
        item = Item(
            name=form.name.data,
            description=form.description.data,
            category=form.category.data,
            user_id=user.id
        )
        session.add(item)
        session.commit()
        flash('Items was added successfully ')
        return redirect(url_for('viewItem', item_id=item.id))
    return render_template('add.html',
                           categories=categories, form=form, title=title)


#   Edit Items page
#   Also check if current user is the owner of that item
@app.route('/edit/<int:item_id>', methods=['POST', 'GET'])
@oidc.require_login
def editItem(item_id):
    title = 'Edit Item'
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    item = session.query(Item).filter_by(id=item_id).first()
    form = ItemForm()
    #   https://stackoverflow.com/a/15939584/2022948
    form.category.choices = [(i, i) for i in categories]
    if item:
        if user.id != item.user_id:
            abort(403)
        if request.method == 'GET':
            form.name.data = item.name
            form.description.data = item.description
            form.category.data = item.category
        if form.validate_on_submit():
            item.name = form.name.data
            item.description = form.description.data
            item.category = form.category.data
            session.add(item)
            session.commit()
            flash('Item updated successfully')
    # return redirect(url_for('viewItem', item_id=item.id))
    else:
        flash("Something went wrong, don't repeat names")
        return render_template('edit.html',
                               item=item, categories=categories,
                               form=form, title=title)
    return render_template('edit.html', item=item,
                           categories=categories, form=form,
                           title=title)


#   View specific Item
#   Also check if current user is the owner of that item
@app.route('/item/<int:item_id>')
@oidc.require_login
def viewItem(item_id):
    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        abort(404)
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    if user.id != item.user_id:
        abort(403)
    else:
        title = '{}'.format(item.name)
        return render_template('item.html', item=item, title=title)


#   Delete Items
#   Also check if current user is the owner of that item
@app.route('/item/delete/<int:item_id>')
@oidc.require_login
def deleteItem(item_id):
    title = 'Item'
    item = session.query(Item).filter_by(id=item_id).first()
    if not item:
        abort(404)
    user = session.query(User).filter_by(
        email=oidc.user_getfield('email')).first()
    if user.id != item.user_id:
        abort(403)
    else:
        session.delete(item)
        session.commit()
        return redirect(url_for('index'))


#   Logout and redirect to index
@app.route("/logout")
def logout():
    oidc.logout()
    return redirect(url_for('index'))


#   Handles error 404
@app.errorhandler(404)
def page_not_found(e):
    title = "Not found (404)"
    return render_template("404_403.html", title=title), 404


#   Handles error 403
@app.errorhandler(403)
def insufficient_permissions(e):
    title = "Sorry, You don't have permission to access this page (403)"
    return render_template("404_403.html", title=title), 403


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
