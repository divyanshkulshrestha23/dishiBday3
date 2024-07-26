from flask import Flask, render_template, redirect, url_for, request, Response
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, LargeBinary
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, URL
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from flask_wtf.file import FileField, FileRequired, FileAllowed
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import boto3
import os

'''
Red underlines? Install the required packages first: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from requirements.txt for this project.
'''


basedir = os.path.abspath(os.path.dirname(__file__))


class Base(DeclarativeBase):
    pass


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
Bootstrap5(app)
db = SQLAlchemy(model_class=Base)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DB_URI')
db.init_app(app)
app.config['UPLOADED_PHOTOS_DEST'] = os.path.join(basedir, 'uploads')
migrate = Migrate(app, db)

photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)
patch_request_class(app)

app.config['AWS_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID')
app.config['AWS_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY')
app.config['S3_BUCKET_NAME'] = os.environ.get('S3_BUCKET_NAME')

def upload_to_s3(file, bucket_name, acl="public-read"):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"]
    )

    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            file.filename,
            ExtraArgs={
                "ACL": acl,
                "ContentType": file.content_type
            }
        )
    except Exception as e:
        print("Something Happened: ", e)
        return e

    return f"https://{bucket_name}.s3.amazonaws.com/{file.filename}"


# CREATE DB
class Memories(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    review: Mapped[str] = mapped_column(String(500), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    ranking: Mapped[int] = mapped_column(Integer, nullable=True)
    image: Mapped[str] = mapped_column(String(500), nullable=False)


# CREATE FORM
class MemoryForm(FlaskForm):
    Description = StringField("What made that moment memorable?", validators=[DataRequired()])
    Rating = StringField("Rate this memory out of 10 (yes, this is a competition)", validators=[DataRequired()])
    submit = SubmitField("Done")


# CREATE FORM 2
class AddMemoryForm(FlaskForm):
    Title = StringField("Your Memory Title", validators=[DataRequired()])
    Description = TextAreaField("What happened in this moment?", validators=[DataRequired()])
    Review = StringField("Something memorable from the moment eg. something that was said or something they did",
                         validators=[DataRequired()])
    photo = FileField(validators=[FileAllowed(photos, 'Image only!'), FileRequired('File was empty!')])
    Rating = StringField("Rate this memory out of 10 (yes, this is a competition)", validators=[DataRequired()])
    submit = SubmitField("Add your memory!")


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    memories = db.session.execute(db.select(Memories).order_by(Memories.rating.asc()))
    allMemories = memories.scalars().all()  # convert ScalarResult to Python List
    rank = 1
    for moment in allMemories:
        moment.ranking = rank
        rank += 1
    db.session.commit()
    return render_template("index.html", memoryList=allMemories)


@app.route("/edit", methods=['GET', 'POST'])
def update():
    form = MemoryForm()
    memoryID = request.args.get('id')
    memorySelected = db.get_or_404(Memories, memoryID)
    if form.validate_on_submit():
        memorySelected.rating = form.Rating.data
        memorySelected.description = form.description.data
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("edit.html", memory=memorySelected, form=form)


@app.route("/delete")
def delete():
    memoryID = request.args.get('id')
    memoryDeleted = db.get_or_404(Memories, memoryID)
    db.session.delete(memoryDeleted)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/add", methods=['GET', 'POST'])
def add():
    form = AddMemoryForm()
    if form.validate_on_submit():
        #file = form.photo.data
        #filename = secure_filename(file.filename)
        #file_path = os.path.join(app.config['UPLOADED_PHOTOS_DEST'], filename)
        #file.save(file_path)
        #filename = photos.save(form.photo.data)
        #file_url = photos.url(filename)
        image_file = form.photo.data
        image_url = upload_to_s3(image_file, app.config["S3_BUCKET_NAME"])
        memoryAdded = Memories(
            title=form.Title.data,
            description=form.Description.data,
            review=form.Review.data,
            image=image_url,
            rating=form.Rating.data
        )
        db.session.add(memoryAdded)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("add.html", form=form)



if __name__ == '__main__':
    app.run(debug=False)
