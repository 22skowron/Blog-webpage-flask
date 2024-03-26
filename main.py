from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from sqlalchemy.exc import IntegrityError
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os
from dotenv import load_dotenv

#########################################################################
    # CREATE APP & CONFIG

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')


PRIVILEGED_USERS = [1]
#########################################################################
    # CREATE DATABASE
class Base(DeclarativeBase):
    pass

#########################################################################
    # INITIALIZE EXTENSIONS

gravatar = Gravatar()
gravatar.init_app(app)

ckeditor = CKEditor()
ckeditor.init_app(app)

bootstrap = Bootstrap5()
bootstrap.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


db = SQLAlchemy(model_class=Base)
db.init_app(app)

#########################################################################
    # ORM CLASSES

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(500), nullable=False)
    nickname: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
        # Relationships
    posts: Mapped[list["BlogPost"]] = relationship(back_populates="author")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
        # Foreign keys
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
        # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
        # Foreign keys
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
        # Relationships
    author: Mapped["User"] = relationship(back_populates="comments")
    post: Mapped["BlogPost"] = relationship(back_populates="comments")


with app.app_context():
    db.create_all()

#########################################################################
    # FUNCTIONS

def admin_only(f):
    @wraps(f)
    @login_required
    def wrapper_function(*args, **kwargs):
        if current_user.id in PRIVILEGED_USERS:
            return f(*args, **kwargs)
        else:
            return abort(code=403)
    return wrapper_function


#########################################################################
    # WEBPAGES

@app.route('/register', methods=['GET', 'POST'])
def register():
    registration_form = RegisterForm()
        # Add new user to a database
    if registration_form.validate_on_submit():
        try:
            new_user = User(
                email=registration_form.email.data,
                password=generate_password_hash(
                    password=registration_form.password.data,
                    method='pbkdf2:sha256',
                    salt_length=8
                ),
                nickname=registration_form.nickname.data
            )
            db.session.add(new_user)
            db.session.commit()
                # Log in the new user
            login_user(new_user)
            flash('Successfully logged in.', 'green')
            return redirect(url_for('get_all_posts'))

        except IntegrityError as ex:
            if '.nickname' in ex.args[0]:
                flash('User with such nickname already exists.')
            elif '.email' in ex.args[0]:
                flash('User with such email already exists. Log in to sign in.')

    elif request.method == 'POST':
        flash('Provide valid data.')

    return render_template("register.html", form=registration_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
        # Log in a user
    if login_form.validate_on_submit():
        user1 = db.session.execute(db.select(User).where(User.email == login_form.email.data)).scalar()
        if user1:
            if check_password_hash(
                password=login_form.password.data,
                pwhash=user1.password
            ):
                login_user(user1)
                flash('Successfully logged in.', 'green')
                return redirect(url_for('get_all_posts'))

            else:
                flash('Wrong password.')
        else:
            flash('No user with such email exists. Register to join in.')

    elif request.method == 'POST':
        flash('Provide valid data.')

    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Successfully logged out.', 'red')
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, privileged=PRIVILEGED_USERS)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if current_user.is_authenticated:
        if comment_form.validate_on_submit():
            new_comment = Comment(
                body=comment_form.body.data,
                author=current_user,
                post=requested_post,
                date=date.today().strftime("%d.%m.%Y")
            )
            db.session.add(new_comment)
            db.session.commit()
            flash("Successfully added a comment.", "green")
            return redirect(url_for("show_post", post_id=post_id))

        elif request.method == "POST":
            flash("Provide valid input.", "red")

    elif not current_user.is_authenticated and request.method == "POST":
        flash("You have to be logged in to enter comments.", "red")

    print(requested_post.comments)
    for comment in requested_post.comments:
        print(comment.body)
    return render_template("post.html", post=requested_post, form=comment_form, privileged=PRIVILEGED_USERS)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

#########################################################################
    # RUN APP

if __name__ == "__main__":
    app.run(debug=True, port=5002)
