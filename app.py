from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user
)
import os

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
login_manager.login_view = "login"   # used only when @login_required is hit

# -------------------------
# Models
# -------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# One‑time DB + default admin
# -------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password="admin123")
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: admin / admin123")
@app.route("/feed")
def feed():
    posts = Post.query.all()
    return render_template("feed.html", posts=posts)

# -------------------------
# PUBLIC routes
# -------------------------
@app.route("/")
def home():
    return render_template("index.html")



# -------------------------
# Auth routes
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        # simple check (no hashing yet)
        if user and user.password == password:
            login_user(user)          # creates session
            next_page = request.args.get("next") or url_for("feed")
            return redirect(next_page)
        else:
            error = "Invalid username or password"
            return render_template("login.html", error=error)

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()                     # clears session
    return redirect(url_for("home"))

# -------------------------
# Example protected route
# -------------------------
@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
