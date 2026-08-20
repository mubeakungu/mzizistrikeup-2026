from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.wallet import Transaction
import uuid

wallet_bp=Blueprint('wallet',__name__,url_prefix='/wallet')
@wallet_bp.get('/')
@login_required
def wallet():
    tx=Transaction.query.filter_by(wallet_id=current_user.wallet.id).order_by(Transaction.id.desc()).limit(50).all()
    return render_template('wallet/wallet.html', transactions=tx)
@wallet_bp.post('/demo-deposit')
@login_required
def demo_deposit():
    amount=Decimal(request.form.get('amount','0'))
    if amount<=0 or amount>100000: flash('Enter a deposit between 1 and 100,000 KES.','error'); return redirect(url_for('wallet.wallet'))
    w=current_user.wallet; w.balance=Decimal(str(w.balance))+amount
    db.session.add(Transaction(wallet_id=w.id,type='demo_deposit',amount=amount,balance_after=w.balance,reference='DEP-'+uuid.uuid4().hex[:10].upper())); db.session.commit()
    flash('Demo deposit credited. Replace this route with M-Pesa Daraja before production.','success'); return redirect(url_for('wallet.wallet'))
