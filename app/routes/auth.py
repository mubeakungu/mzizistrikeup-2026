from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from app.extensions import db
from app.models.user import User
from app.models.wallet import Wallet, Transaction
import uuid

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('luck2x.lobby'))
    if request.method == 'POST':
        username=request.form.get('username','').strip()
        phone=request.form.get('phone','').strip() or None
        password=request.form.get('password','')
        if len(username)<3 or len(password)<6: flash('Username must be 3+ characters and password 6+ characters.','error')
        elif User.query.filter_by(username=username).first(): flash('Username already exists.','error')
        else:
            u=User(username=username, phone=phone); u.set_password(password); db.session.add(u); db.session.flush()
            w=Wallet(user_id=u.id,balance=1000); db.session.add(w)
            db.session.add(Transaction(wallet_id=w.id,type='bonus',amount=1000,balance_after=1000,reference='WELCOME-'+uuid.uuid4().hex[:10].upper()))
            db.session.commit(); login_user(u); return redirect(url_for('luck2x.lobby'))
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip()).first()
        if u and u.check_password(request.form.get('password','')): login_user(u); return redirect(url_for('luck2x.lobby'))
        flash('Invalid username or password.','error')
    return render_template('auth/login.html')

@auth_bp.get('/logout')
def logout(): logout_user(); return redirect(url_for('auth.login'))
