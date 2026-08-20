from flask import Flask, redirect, url_for, render_template
from app.extensions import db, login_manager
from config import config

def create_app(config_name='development'):
    app=Flask(__name__); app.config.from_object(config[config_name]); db.init_app(app); login_manager.init_app(app); login_manager.login_view='auth.login'
    from app.models.user import User
    from app.models.wallet import Wallet, Transaction
    from app.models.luck2x import Luck2xGameRound, Luck2xBet
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User,int(user_id))
    from app.routes.auth import auth_bp
    from app.routes.wallet import wallet_bp
    from app.routes.luck2x_games import luck2x_bp
    app.register_blueprint(auth_bp); app.register_blueprint(wallet_bp); app.register_blueprint(luck2x_bp)
    @app.get('/')
    def home(): return redirect(url_for('luck2x.lobby'))
    @app.context_processor
    def inject_globals(): return {'app_name':'Mzizibet'}
    with app.app_context(): db.create_all()
    return app
