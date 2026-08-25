import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-change-me"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///onlyogs.db")
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ===========================
# MODELS
# ===========================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    posts = db.relationship("Post", backref="user", lazy=True)
    comments = db.relationship("Comment", backref="user", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    likes = db.relationship("Like", backref="post", lazy=True)
    comments = db.relationship("Comment", backref="post", lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class GhostMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_viewed = db.Column(db.Boolean, default=False)
    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_ghost_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="received_ghost_messages")

class VoiceLounge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    creator = db.relationship("User", backref="created_lounges")
    participants = db.relationship("VoiceLoungeParticipant", backref="lounge", cascade="all, delete-orphan")

class VoiceLoungeParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lounge_id = db.Column(db.Integer, db.ForeignKey("voice_lounge.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_speaking = db.Column(db.Boolean, default=False)
    user = db.relationship("User", backref="voice_lounge_participations")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ===========================
# ROOT ROUTE
# ===========================

@app.route("/")
def index():
    return render_template("login.html")

# ===========================
# AUTH ROUTES
# ===========================

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
        if not user or not check_password_hash(user.password, password):
            return render_template("login.html", error="Invalid username or password")
        login_user(user)
        return redirect(url_for("feed"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ===========================
# FEED ROUTES
# ===========================

@app.route("/feed")
@login_required
def feed():
    formatted_posts = []
    posts = Post.query.order_by(Post.created_at.desc()).all()
    for post in posts:
        likes_count = Like.query.filter_by(post_id=post.id).count()
        formatted_posts.append({"id": post.id, "user": post.user, "content": post.content, "created_at": post.created_at, "likes": likes_count, "comments": post.comments})
    return render_template("feed.html", posts=formatted_posts, user=current_user)

@app.route("/create-post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        body = request.form.get("body")
        if body:
            post = Post(user_id=current_user.id, content=body)
            db.session.add(post)
            db.session.commit()
            return redirect(url_for("feed"))
        return render_template("create_post.html")
    return render_template("create_post.html")

@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
    db.session.commit()
    return redirect(url_for("feed"))

@app.route("/user/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    return render_template("profile.html", user=user, posts=posts)

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
    expires_at = now + timedelta(seconds=ttl_seconds)
    ghost_msg = GhostMessage(sender_id=current_user.id, recipient_id=recipient.id, content=content, created_at=now, expires_at=expires_at)
    db.session.add(ghost_msg)
    db.session.commit()
    return redirect(url_for("ghost_messages"))

@app.route("/ghost-messages")
@login_required
def ghost_messages():
    now = datetime.utcnow()
    messages = GhostMessage.query.filter((GhostMessage.recipient_id == current_user.id) & (GhostMessage.expires_at > now)).all()
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

# ===========================
# VOICE LOUNGE ROUTES
# ===========================

@app.route("/create-lounge", methods=["GET", "POST"])
@login_required
def create_lounge():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        if not name:
            return render_template("create_lounge.html", error="Lounge name required")
        lounge = VoiceLounge(name=name, description=description, creator_id=current_user.id)
        db.session.add(lounge)
        db.session.commit()
        return redirect(url_for("voice_lounges"))
    return render_template("create_lounge.html")

@app.route("/voice-lounges")
@login_required
def voice_lounges():
    active_lounges = VoiceLounge.query.filter_by(is_active=True).all()
    lounges_with_speakers = []
    for lounge in active_lounges:
        speaker_count = VoiceLoungeParticipant.query.filter_by(lounge_id=lounge.id).count()
        lounges_with_speakers.append({"lounge": lounge, "speaker_count": speaker_count, "participants": lounge.participants})
    return render_template("voice_lounges.html", lounges=lounges_with_speakers)

@app.route("/join-lounge/<int:lounge_id>", methods=["POST"])
@login_required
def join_lounge(lounge_id):
    lounge = VoiceLounge.query.get(lounge_id)
    if not lounge or not lounge.is_active:
        return redirect(url_for("voice_lounges"))
    existing = VoiceLoungeParticipant.query.filter_by(lounge_id=lounge_id, user_id=current_user.id).first()
    if not existing:
        participant = VoiceLoungeParticipant(lounge_id=lounge_id, user_id=current_user.id)
        db.session.add(participant)
        db.session.commit()
    return redirect(url_for("lounge_detail", lounge_id=lounge_id))

@app.route("/lounge/<int:lounge_id>")
@login_required
def lounge_detail(lounge_id):
    lounge = VoiceLounge.query.get(lounge_id)
    if not lounge or not lounge.is_active:
        return redirect(url_for("voice_lounges"))
    participants = VoiceLoungeParticipant.query.filter_by(lounge_id=lounge_id).all()
    is_participant = any(p.user_id == current_user.id for p in participants)
    return render_template("lounge_detail.html", lounge=lounge, participants=participants, is_participant=is_participant)

@app.route("/leave-lounge/<int:lounge_id>", methods=["POST"])
@login_required
def leave_lounge(lounge_id):
    participant = VoiceLoungeParticipant.query.filter_by(lounge_id=lounge_id, user_id=current_user.id).first()
    if participant:
        db.session.delete(participant)
        db.session.commit()
    return redirect(url_for("voice_lounges"))

@app.route("/toggle-speaking/<int:lounge_id>", methods=["POST"])
@login_required
def toggle_speaking(lounge_id):
    participant = VoiceLoungeParticipant.query.filter_by(lounge_id=lounge_id, user_id=current_user.id).first()
    if participant:
        participant.is_speaking = not participant.is_speaking
        db.session.commit()
    return redirect(url_for("lounge_detail", lounge_id=lounge_id))

@app.route("/close-lounge/<int:lounge_id>", methods=["POST"])
@login_required
def close_lounge(lounge_id):
    lounge = VoiceLounge.query.get(lounge_id)
    if lounge and lounge.creator_id == current_user.id:
        lounge.is_active = False
        db.session.commit()
    return redirect(url_for("voice_lounges"))

# ===========================
# RUN APP
# ===========================

@app.route("/initdb")
def initdb():
    db.create_all()
    return "Database initialized!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
