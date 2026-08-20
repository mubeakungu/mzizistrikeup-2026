from datetime import datetime
from app.extensions import db

class Luck2xGameRound(db.Model):
    __tablename__ = 'luck2x_game_rounds'
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(30), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    bet = db.Column(db.Numeric(12,2), nullable=False)
    state = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), default='active', index=True)
    payout = db.Column(db.Numeric(12,2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

class Luck2xBet(db.Model):
    __tablename__ = 'luck2x_bets'
    id = db.Column(db.Integer, primary_key=True)
    game = db.Column(db.String(30), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    round_id = db.Column(db.Integer, db.ForeignKey('luck2x_game_rounds.id'))
    bet = db.Column(db.Numeric(12,2), nullable=False)
    result = db.Column(db.JSON, default=dict)
    status = db.Column(db.String(20), default='settled')
    payout = db.Column(db.Numeric(12,2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
