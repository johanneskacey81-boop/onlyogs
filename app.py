from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

# -------------------------
# App + DB setup
# -------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///onlyogs.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------
# Login manager
# -------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -------------------------
# Models
# -------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref="posts")

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    user = db.relationship("User", backref="comments")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# DB + default admin
# -------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@onlyogs.com",
            password=generate_password_hash("admin123")
        )
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: admin / admin123")

# -------------------------
# Helpers
# -------------------------
def post_like_count(post_id):
    return Like.query.filter_by(post_id=post_id).count()

def post_comments(post_id):
    return Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()

# -------------------------
# PUBLIC routes
# -------------------------
@app.route("/")
def home():
    return redirect("/feed")

@app.route("/feed")
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    data = []
    for p in posts:
        data.append({
            "post": p,
            "likes": post_like_count(p.id),
            "comments": post_comments(p.id)
        })
    return render_template(
        "feed.html",
        posts=data,
        user=current_user if current_user.is_authenticated else None
    )

# -------------------------
# Auth routes
# -------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            return render_template("signup.html", error="Username already taken")
        
        if User.query.filter_by(email=email).first():
            return render_template("signup.html", error="Email already registered")

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for("feed"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get("next") or url_for("feed")
            return redirect(next_page)
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# -------------------------
# Posting
# -------------------------
@app.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        body = request.form.get("body")
        if body:
            post = Post(body=body, user_id=current_user.id)
            db.session.add(post)
            db.session.commit()
        return redirect(url_for("feed"))
    
    return render_template("create_post.html")

# -------------------------
# Likes
# -------------------------
@app.route("/like/<int:post_id>")
@login_required
def like(post_id):
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not existing:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
    return redirect(request.referrer or url_for("feed"))

# -------------------------
# Comments
# -------------------------
@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment(post_id):
    body = request.form.get("body")
    if body:
        c = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(c)
        db.session.commit()
    return redirect(request.referrer or url_for("feed"))

# -------------------------
# Profiles
# -------------------------
@app.route("/user/<username>")
def user_profile(username):
    user_obj = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user_obj.id).order_by(Post.created_at.desc()).all()
    data = []
    for p in posts:
        data.append({
            "post": p,
            "likes": post_like_count(p.id),
            "comments": post_comments(p.id)
        })
    return render_template(
        "profile.html",
        profile_user=user_obj,
        posts=data,
        user=current_user if current_user.is_authenticated else None
    )

# -------------------------
# Run (Render compatible)
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
