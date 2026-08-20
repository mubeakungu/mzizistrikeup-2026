from datetime import datetime
from app.extensions import db

class Wallet(db.Model):
    __tablename__ = 'wallets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    balance = db.Column(db.Numeric(12,2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Numeric(12,2), nullable=False)
    balance_after = db.Column(db.Numeric(12,2), nullable=False)
    reference = db.Column(db.String(80), unique=True, nullable=False)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
