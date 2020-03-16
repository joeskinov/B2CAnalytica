#!/Library/Frameworks/Python.framework/Versions/3.7/bin/python3
import os
from flask import Flask, jsonify, url_for, redirect, render_template, request, abort, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user
from flask_security.utils import encrypt_password
import flask_admin
from flask_admin.contrib import sqla
from flask_admin import helpers as admin_helpers
from flask_admin import BaseView, expose
from flask_sockets import Sockets

import pandas as pd
from Twitter import Twitter
from Analyse import Analyse

import csv

csv_columns = ['tweet_id', 'sentiment', 'confidence', 'username', 'created', 'location', 'text']

#define file upload folder and extensions
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = set(['txt', 'csv'])

#twitter authntication
twitter = Twitter("9jZwbeNcxoRd9BMS2SrRBCNls", "Tbhae7JDjfpDRvb1XFxlCvNB4KIJXgxzOcQzkvqVRY77HDhjqR", "896463626076401664-3j9DGMoxuxFu9OjsXe2iX19R6bhWVkQ", "R0Y4YB4fYQ3CSrDz1Qfj9o4eHB09F2zIwUp1mqi9L1OnE")
#print(twitter.get_timeline("zanguejoel"))

# Create Flask application
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)
sockets = Sockets(app)


# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)

#check upload file types
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))

    def __str__(self):
        return self.email

class RawDataSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(255))
    source = db.Column(db.String(90))
    data = db.Column(db.PickleType())

    def __str__(self):
        return self.user_name

class AnalysedDataSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(255))
    raw_data_id = db.Column(db.String(90))
    data = db.Column(db.PickleType())

    def __str__(self):
        return self.user_name

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


# Create customized model view class
class MyModelView(sqla.ModelView):

    def is_accessible(self):
        if not current_user.is_active or not current_user.is_authenticated:
            return False

        if current_user.has_role('superuser'):
            return True

        return False

    def _handle_view(self, name, **kwargs):
        """
        Override builtin _handle_view in order to redirect users when a view is not accessible.
        """
        if not self.is_accessible():
            if current_user.is_authenticated:
                # permission denied
                abort(403)
            else:
                # login
                return redirect(url_for('security.login', next=request.url))


    # can_edit = True
    edit_modal = True
    create_modal = True    
    can_export = True
    can_view_details = True
    details_modal = True

class UserView(MyModelView):
    column_editable_list = ['email', 'first_name', 'last_name']
    column_searchable_list = column_editable_list
    column_exclude_list = ['password']
    # form_excluded_columns = column_exclude_list
    column_details_exclude_list = column_exclude_list
    column_filters = column_editable_list


class CustomView(BaseView):
    @expose('/')
    def index(self):
        return self.render('admin/custom_index.html')

#Simple tweets ant content analysis
class SentimentView(BaseView):
    @expose('/')
    def index(self):
        data_sets = AnalysedDataSet.query.all()
        return self.render('admin/tags_index.html')
    #form to get data from users
    @expose('/upload_data', methods=['GET', 'POST'])
    def upload_data(self):
        if request.method == 'POST':
            data_source = request.form.get('source')
            username = request.form.get('username')
            source = request.form.get('datafrom')

            if username=='':
                flash('No username')
                return redirect(request.url)
            
            if data_source == 'file':
                # check if the post request has the file part
                if 'file' not in request.files:
                    flash('No file part')
                    return redirect(request.url)
                file = request.files['file']
                # if user does not select file, browser also
                # submit an empty part without filename
                if file.filename == '':
                    flash('No selected file')
                    return redirect(request.url)
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    flash('File uploaded')
                    df = pd.read_csv(UPLOAD_FOLDER + filename, usecols=['text','username'])
                    result = df.to_dict(orient='records')
                    
                    raw_dataset = RawDataSet(user_name=username, source=source, data=result)
                    db.session.add(raw_dataset)
                    db.session.commit()
                    return redirect(url_for('tags.translate', id=raw_dataset.id))

            if data_source == 'twitter':
                raw_dataset = RawDataSet(user_name=username, source=source, data=twitter.get_timeline(username, 20))
                db.session.add(raw_dataset)
                db.session.commit()
                return redirect(url_for('tags.translate', id=raw_dataset.id))
        return self.render('admin/tags_index.html')
    #view to translate and display translated tweets in en
    @expose('/translate/<id>')
    def translate(self, id):
        raw_data = RawDataSet.query.get(id)
        rawdata = raw_data.data
        username = raw_data.user_name
        data_length=len(rawdata)
        #learn.predict("I really loved the flight")
        return self.render('admin/data_translate.html', username=username ,rawdata=rawdata, dataset_id=id, data_length=data_length)
    #view to analyse and display analysis result of each tweet
    @expose('/analysis/<id>')
    def analysis(self, id):
        raw_data = RawDataSet.query.get(id)
        rawdata = raw_data.data
        username = raw_data.user_name
        data_length=len(rawdata)
        analyser = Analyse(folder_path="./twitter-data", model_file="trained_model")
        analysed_data = analyser.predict_sentiment(dataset=rawdata)

        #Save the analysed data
        a_dataset = AnalysedDataSet(raw_data_id=id, user_name=username, data=analysed_data)
        db.session.add(a_dataset)
        db.session.commit()

        return self.render('admin/data_analyse.html', username=username ,rawdata=analysed_data, dataset_id=id, Ÿdata_length=data_length)
    
    @expose('/analysis_view/<id>')
    def analysis_view(self, id):
        analysed_data = AnalysedDataSet.query.get(id)
        analyseddata = analysed_data.data
        username = analysed_data.user_name
        data_length=len(analyseddata)
        return self.render('admin/data_analyse.html', username=username ,rawdata=analyseddata, dataset_id=id, data_length=data_length)
    
    @expose('/getresults/<id>')
    def getresults(self, id):
        analysed_data = AnalysedDataSet.query.get(id)
        analyseddata = analysed_data.data
        print(analyseddata[0])
        return jsonify(result=analyseddata)

    @expose('/results_view/<id>')
    def results_view(self, id):
        analysed_data = AnalysedDataSet.query.get(id)
        analyseddata = analysed_data.data
        username = analysed_data.user_name
        data_length=len(analyseddata)
        return self.render('admin/display_results.html', username=username ,rawdata=analyseddata, dataset_id=id, data_length=data_length)

#class to manage tweet comments analysis
class CommentsSentimentView(BaseView):
    @expose('/')
    def index(self):
        return self.render('admin/comments_index.html')
    @expose('/comments_data', methods=['GET', 'POST'])
    def comments_data(self):
        if request.method == 'POST':
            data_source = request.form.get('source')
            username = request.form.get('username')
            source = request.form.get('datafrom')

            if username=='':
                flash('No username')
                return redirect(request.url)
            
            if data_source == 'twitter':
                #print(twitter.get_user_replies(username, 20, 50))
                raw_dataset = RawDataSet(user_name=username, source=source, data=twitter.get_user_replies(username, 20, 20))
                db.session.add(raw_dataset)
                db.session.commit()
                return redirect(url_for('tags.translate', id=raw_dataset.id))
        return self.render('admin/comments_index.html')

#class to manage root time content analysis
class RealTimeView(BaseView):
    @expose('/')
    def index(self):
        return self.render('admin/comments_index.html')

    @expose('/realtime', methods=['GET', 'POST'])
    def realtime(self):
        if request.method == 'POST':
            data_source = request.form.get('source')
            username = request.form.get('username')
            if username=='':
                flash('No username')
                return redirect(request.url)
            if data_source == 'twitter':
                print(twitter.get_user_replies(username, 20))
        return self.render('admin/comments_index.html')
    
    @expose('/stream/<username>')
    def analysis(self, username):
        return self.render('admin/data_analyse.html', username=username)

    @sockets.route('/stream_tweets')
    def stream_tweets(self, ws):
        while not ws.closed:
            message = ws.receive()
            ws.send(message)

#class to manage visualization of uploaded datasets
class DataSetsView(BaseView):
    @expose('/')
    def index(self):
        # Get all datasets
        #num_rows_deleted = db.session.query(RawDataSet).delete()
        #db.session.commit()
        data_sets = RawDataSet.query.all()
        return self.render('admin/datasets.html', datasets=data_sets)
#class to manage visualization of uploaded datasets
class AnalysedDataView(BaseView):
    @expose('/')
    def index(self):
        # Get all datasets
        #num_rows_deleted = db.session.query(AnalysedDataSet).delete()
        #db.session.commit()
        data_sets = AnalysedDataSet.query.all()
        return self.render('admin/analyseddata.html', datasets=data_sets)

# Flask views
@app.route('/')
def index():
    return render_template('index.html')


# Create admin
admin = flask_admin.Admin(
    app,
    'B2C Analytica',
    base_template='my_master.html',
    template_mode='bootstrap3',
)

# Add model views
admin.add_view(MyModelView(Role, db.session, menu_icon_type='fa', menu_icon_value='fa-server'))
admin.add_view(UserView(User, db.session, menu_icon_type='fa', menu_icon_value='fa-users', name="Users"))
admin.add_view(SentimentView(name="Get Data", endpoint='tags', menu_icon_type='fa', menu_icon_value='fa-connectdevelop',))
admin.add_view(CommentsSentimentView(name="User Comments", endpoint='comments', menu_icon_type='fa', menu_icon_value='fa-connectdevelop',))
admin.add_view(DataSetsView(name="Datasets", endpoint='datasets', menu_icon_type='fa', menu_icon_value='fa-connectdevelop',))
admin.add_view(AnalysedDataView(name="Analysed data", endpoint='analyseddata', menu_icon_type='fa', menu_icon_value='fa-connectdevelop',))
#admin.add_view(RealTimeView(name="Realtime", endpoint='live', menu_icon_type='fa', menu_icon_value='fa-connectdevelop',))

# define a context processor for merging flask-admin's template context into the
# flask-security views.
@security.context_processor
def security_context_processor():
    return dict(
        admin_base_template=admin.base_template,
        admin_view=admin.index_view,
        h=admin_helpers,
        get_url=url_for
    )

def build_sample_db():
    """
    Populate a small db with some example entries.
    """

    import string
    import random

    db.drop_all()
    db.create_all()

    with app.app_context():
        user_role = Role(name='user')
        super_user_role = Role(name='superuser')
        db.session.add(user_role)
        db.session.add(super_user_role)
        db.session.commit()

        test_user = user_datastore.create_user(
            first_name='Admin',
            email='admin',
            password=encrypt_password('admin'),
            roles=[user_role, super_user_role]
        )

        first_names = [
            'Harry', 'Amelia', 'Oliver', 'Jack', 'Isabella', 'Charlie', 'Sophie', 'Mia',
            'Jacob', 'Thomas', 'Emily', 'Lily', 'Ava', 'Isla', 'Alfie', 'Olivia', 'Jessica',
            'Riley', 'William', 'James', 'Geoffrey', 'Lisa', 'Benjamin', 'Stacey', 'Lucy'
        ]
        last_names = [
            'Brown', 'Smith', 'Patel', 'Jones', 'Williams', 'Johnson', 'Taylor', 'Thomas',
            'Roberts', 'Khan', 'Lewis', 'Jackson', 'Clarke', 'James', 'Phillips', 'Wilson',
            'Ali', 'Mason', 'Mitchell', 'Rose', 'Davis', 'Davies', 'Rodriguez', 'Cox', 'Alexander'
        ]

        for i in range(len(first_names)):
            tmp_email = first_names[i].lower() + "." + last_names[i].lower() + "@example.com"
            tmp_pass = ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(10))
            user_datastore.create_user(
                first_name=first_names[i],
                last_name=last_names[i],
                email=tmp_email,
                password=encrypt_password(tmp_pass),
                roles=[user_role, ]
            )
        db.session.commit()
    return

if __name__ == '__main__':

    # Build a sample db on the fly, if one does not exist yet.
    app_dir = os.path.realpath(os.path.dirname(__file__))
    database_path = os.path.join(app_dir, app.config['DATABASE_FILE'])
    if not os.path.exists(database_path):
        build_sample_db()

    # Start app
    app.run(debug=True)