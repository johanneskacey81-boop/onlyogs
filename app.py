import os
from datetime import datetime
from flask import Flask, render_template, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///onlyogs.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# -------------------------
# MODELS
# -------------------------

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    posts = db.relationship("Post", backref="user", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    comments = db.relationship("Comment", backref="post", lazy=True)
    likes = db.relationship("Like", backref="post", lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))

# -------------------------
# LOGIN MANAGER
# -------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create admin if missing
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

# -------------------------
# ROOT ROUTE
# -------------------------

@app.route("/")
def index():
   return render_template("login.html")

# -------------------------
# AUTH ROUTES
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
        return redirect("/feed")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            return render_template("login.html", error="Invalid username or password")

        login_user(user)
        return redirect("/feed")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# -------------------------
# FEED
# -------------------------
@login_required
@app.route("/feed")
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()

    formatted_posts = []
    for post in posts:
        formatted_posts.append({
            "post": post,
            "likes": len(post.likes),
            "comments": post.comments
        })

    return render_template("feed.html", posts=formatted_posts, user=current_user)

# -------------------------
# CREATE POST
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
            return redirect("/feed")

    return render_template("create_post.html")

# -------------------------
# LIKE POST
# -------------------------

@app.route("/like/<int:post_id>")
@login_required
def like(post_id):
    existing_like = Like.query.filter_by(
        user_id=current_user.id, post_id=post_id
    ).first()

    if not existing_like:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()

    return redirect("/feed")

# -------------------------
# USER PROFILE
# -------------------------

@app.route("/user/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template("profile.html", user=user, posts=posts)

# -------------------------
# RUN APP
# -------------------------
@app.route("/initdb")
def initdb():
    db.create_all()
    return "Database initialized!"

# ===========================
# GHOST MODE ROUTES
# ===========================

@app.route("/send-ghost-message", methods=["POST"])
@login_required
def send_ghost_message():
    recipient_username = request.form.get("recipient")
    content = request.form.get("content")
    ttl_seconds = int(request.form.get("ttl", 30))
    
    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        return redirect(url_for("feed"))
    
    expires_at = datetime.utcnow() + datetime.timedelta(seconds=ttl_seconds)
    
    ghost_msg = GhostMessage(
        sender_id=current_user.id,
        recipient_id=recipient.id,
        content=content,
        expires_at=expires_at
    )
    
    db.session.add(ghost_msg)
    db.session.commit()
    
    return redirect(url_for("feed"))


@app.route("/ghost-messages")
@login_required
def ghost_messages():
    now = datetime.utcnow()
    messages = GhostMessage.query.filter(
        (GhostMessage.recipient_id == current_user.id) &
        (GhostMessage.expires_at > now)
    ).all()
    
    expired = GhostMessage.query.filter(GhostMessage.expires_at <= now).delete()
    db.session.commit()
    
    return render_template("ghost_messages.html", messages=messages)


@app.route("/view-ghost-message/<int:message_id>")
@login_required
def view_ghost_message(message_id):
    msg = GhostMessage.query.get(message_id)
    
    if not msg or msg.recipient_id != current_user.id:
        return redirect(url_for("feed"))
    
    if datetime.utcnow() > msg.expires_at:
        db.session.delete(msg)
        db.session.commit()
        return "Message expired!"
    
    msg.is_viewed = True
    db.session.commit()
    
    return render_template("view_ghost_message.html", message=msg)


@app.route("/delete-ghost-message/<int:message_id>", methods=["POST"])
@login_required
def delete_ghost_message(message_id):
    msg = GhostMessage.query.get(message_id)
    if msg and msg.recipient_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
    return redirect(url_for("ghost_messages"))
# ===========================
# GHOST MODE MODEL
# ===========================
# ===========================
# GHOST MODE MODEL
# ===========================

class GhostMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_viewed = db.Column(db.Boolean, default=False)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_ghost_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_ghost_messages')


# ===========================
# GHOST MODE ROUTES
# ===========================

@app.route("/send-ghost-message", methods=["POST"])
@login_required
def send_ghost_message():
    recipient_username = request.form.get("recipient")
    content = request.form.get("content")
    ttl_seconds = int(request.form.get("ttl", 30))
    
    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        return redirect(url_for("feed"))
    
    now = datetime.utcnow()
    expires_at = now + datetime.timedelta(seconds=ttl_seconds)
    
    ghost_msg = GhostMessage(
        sender_id=current_user.id,
        recipient_id=recipient.id,
        content=content,
        created_at=now,
        expires_at=expires_at
    )
    
    db.session.add(ghost_msg)
    db.session.commit()
    
    return redirect(url_for("ghost_messages"))


@app.route("/ghost-messages")
@login_required
def ghost_messages():
    now = datetime.utcnow()
    messages = GhostMessage.query.filter(
        (GhostMessage.recipient_id == current_user.id) &
        (GhostMessage.expires_at > now)
    ).all()
    
    expired = GhostMessage.query.filter(GhostMessage.expires_at <= now).delete()
    db.session.commit()
    
    return render_template("ghost_messages.html", messages=messages, now=now)


@app.route("/view-ghost-message/<int:message_id>")
@login_required
def view_ghost_message(message_id):
    msg = GhostMessage.query.get(message_id)
    
    if not msg or msg.recipient_id != current_user.id:
        return redirect(url_for("feed"))
    
    now = datetime.utcnow()
    if now > msg.expires_at:
        db.session.delete(msg)
        db.session.commit()
        return "Message expired!"
    
    msg.is_viewed = True
    db.session.commit()
    
    return render_template("view_ghost_message.html", message=msg)


@app.route("/delete-ghost-message/<int:message_id>", methods=["POST"])
@login_required
def delete_ghost_message(message_id):
    msg = GhostMessage.query.get(message_id)
    if msg and msg.recipient_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
    return redirect(url_for("ghost_messages"))

