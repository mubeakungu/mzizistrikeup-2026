import hashlib
import hmac
import math
import secrets
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.luck2x import Luck2xGameRound, Luck2xBet
from app.models.wallet import Transaction

luck2x_bp = Blueprint("luck2x", __name__, url_prefix="/games")


GAMES = {
    "crash": {"name": "Crash", "path": "crash", "description": "Cash out before the multiplier crashes."},
    "mines": {"name": "Mines", "path": "mines", "description": "Reveal safe tiles and avoid the mines."},
    "tower": {"name": "Tower", "path": "tower", "description": "Climb ten levels without hitting a bomb."},
    "dice": {"name": "Dice", "path": "dice", "description": "Predict the roll and choose your payout."},
    "battle": {"name": "Battle", "path": "battle", "description": "Roll against the house and take the higher result."},
    "wheel": {"name": "Wheel", "path": "wheel", "description": "Pick a colour and spin for a multiplier."},
    "hilo": {"name": "HiLo", "path": "hilo", "description": "Predict whether the next card is higher or lower."},
}


def _money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def _wallet():
    return current_user.wallet


def _debit(amount, game):
    amount = _money(amount)
    wallet = _wallet()
    if Decimal(str(wallet.balance)) < amount:
        return False, "Insufficient wallet balance."
    wallet.balance = _money(wallet.balance) - amount
    db.session.add(Transaction(
        wallet_id=wallet.id,
        type="bet",
        amount=-amount,
        balance_after=wallet.balance,
        reference=f"{game.upper()}-{uuid.uuid4().hex[:10].upper()}",
        status="completed",
    ))
    return True, None


def _credit(amount, game):
    amount = _money(amount)
    if amount <= 0:
        return
    wallet = _wallet()
    wallet.balance = _money(wallet.balance) + amount
    db.session.add(Transaction(
        wallet_id=wallet.id,
        type="win",
        amount=amount,
        balance_after=wallet.balance,
        reference=f"{game.upper()}-{uuid.uuid4().hex[:10].upper()}",
        status="completed",
    ))


def _active(game):
    return Luck2xGameRound.query.filter_by(
        user_id=current_user.id, game=game, status="active"
    ).order_by(Luck2xGameRound.id.desc()).first()


def _finish(round_, status, payout=Decimal("0")):
    round_.status = status
    round_.payout = _money(payout)
    round_.finished_at = datetime.utcnow()


def _fair_int(seed, label, modulo):
    digest = hmac.new(seed.encode(), label.encode(), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") % modulo


def _fair_unit(seed, label):
    return _fair_int(seed, label, 10_000_000) / 10_000_000.0


def _age_ok():
    try:
        return bool(current_user.can_play()[0])
    except Exception:
        return True


@luck2x_bp.get("/")
@login_required
def lobby():
    return render_template("games/luck2x/lobby.html", games=list(GAMES.values()))


@luck2x_bp.get("/<game>")
@login_required
def game_page(game):
    if game not in GAMES:
        return "Game not found", 404
    return render_template("games/luck2x/game.html", game=GAMES[game])


# ------------------------------ Crash ------------------------------
@luck2x_bp.post("/crash/start")
@login_required
def crash_start():
    if not _age_ok():
        return jsonify(ok=False, error="You are not eligible to play."), 403
    if _active("crash"):
        return jsonify(ok=False, error="Finish your current Crash round first.")
    bet = _money(request.json.get("bet", 0))
    if bet <= 0:
        return jsonify(ok=False, error="Enter a valid bet.")
    ok, err = _debit(bet, "crash")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400

    seed = secrets.token_hex(32)
    # House-edge distribution: heavy tail, minimum 1.00x.
    u = max(_fair_unit(seed, "crash"), 1e-7)
    crash_at = max(1.0, math.floor((0.97 / u) * 100) / 100)
    round_ = Luck2xGameRound(
        game="crash", user_id=current_user.id, bet=bet,
        state={"seed": seed, "crash_at": crash_at, "multiplier": 1.0}
    )
    db.session.add(round_)
    db.session.commit()
    return jsonify(ok=True, id=round_.id, multiplier=1.0, crash_at=crash_at)


@luck2x_bp.post("/crash/cashout")
@login_required
def crash_cashout():
    round_ = _active("crash")
    if not round_:
        return jsonify(ok=False, error="No active Crash round."), 400
    multiplier = max(1.0, float(request.json.get("multiplier", 1)))
    crash_at = float(round_.state["crash_at"])
    if multiplier >= crash_at:
        _finish(round_, "lost", 0)
        db.session.commit()
        return jsonify(ok=False, crashed=True, payout=0, balance=float(_wallet().balance))
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(multiplier)))
    _credit(payout, "crash")
    _finish(round_, "cashed", payout)
    db.session.commit()
    return jsonify(ok=True, payout=float(payout), balance=float(_wallet().balance))


# ------------------------------ Mines ------------------------------
@luck2x_bp.post("/mines/start")
@login_required
def mines_start():
    if _active("mines"):
        return jsonify(ok=False, error="Finish your current Mines round first.")
    bet = _money(request.json.get("bet", 0))
    bombs = int(request.json.get("bombs", 3))
    if bet <= 0 or bombs < 1 or bombs > 24:
        return jsonify(ok=False, error="Bet must be positive and bombs must be 1-24."), 400
    ok, err = _debit(bet, "mines")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    cells = list(range(25))
    # Deterministic Fisher-Yates shuffle from server seed.
    for i in range(24, 0, -1):
        j = _fair_int(seed, f"mine-{i}", i + 1)
        cells[i], cells[j] = cells[j], cells[i]
    mines = cells[:bombs]
    round_ = Luck2xGameRound(
        game="mines", user_id=current_user.id, bet=bet,
        state={"seed": seed, "mines": mines, "opened": []}
    )
    db.session.add(round_)
    db.session.commit()
    return jsonify(ok=True, id=round_.id, cells=25, bombs=bombs, opened=[])


@luck2x_bp.post("/mines/open")
@login_required
def mines_open():
    round_ = _active("mines")
    if not round_:
        return jsonify(ok=False, error="No active Mines round."), 400
    cell = int(request.json.get("cell", -1))
    if cell < 0 or cell > 24:
        return jsonify(ok=False, error="Invalid tile."), 400
    state = round_.state
    opened = list(state.get("opened", []))
    if cell in opened:
        return jsonify(ok=False, error="Tile already opened."), 400
    opened.append(cell)
    state["opened"] = opened
    round_.state = state
    if cell in state["mines"]:
        _finish(round_, "lost", 0)
        db.session.commit()
        return jsonify(ok=True, hit=True, opened=opened, payout=0, balance=float(_wallet().balance))
    safe = 25 - len(state["mines"])
    multiplier = max(1.01, round((1 - 0.035) * math.comb(25 - len(opened), safe - len(opened)) / math.comb(25, safe), 4) ** -1)
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(multiplier)))
    round_.state = state
    db.session.commit()
    return jsonify(ok=True, hit=False, opened=opened, multiplier=multiplier, claim=float(payout))


@luck2x_bp.post("/mines/claim")
@login_required
def mines_claim():
    round_ = _active("mines")
    if not round_:
        return jsonify(ok=False, error="No active Mines round."), 400
    opened = len(round_.state.get("opened", []))
    if opened < 1:
        return jsonify(ok=False, error="Open at least one tile."), 400
    bombs = len(round_.state["mines"])
    safe = 25 - bombs
    # Exact fair-style cumulative multiplier with a 3.5% house edge.
    prob = 1.0
    for i in range(opened):
        prob *= (safe - i) / (25 - i)
    multiplier = round(0.965 / prob, 4)
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(multiplier)))
    _credit(payout, "mines")
    _finish(round_, "won", payout)
    db.session.commit()
    return jsonify(ok=True, payout=float(payout), multiplier=multiplier, balance=float(_wallet().balance))


# ------------------------------ Tower ------------------------------
@luck2x_bp.post("/tower/start")
@login_required
def tower_start():
    if _active("tower"):
        return jsonify(ok=False, error="Finish your current Tower round first.")
    bet = _money(request.json.get("bet", 0))
    bombs = int(request.json.get("bombs", 1))
    if bet <= 0 or bombs not in (1, 2, 3, 4):
        return jsonify(ok=False, error="Choose 1-4 bombs.")
    ok, err = _debit(bet, "tower")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    round_ = Luck2xGameRound(
        game="tower", user_id=current_user.id, bet=bet,
        state={"seed": seed, "bombs": bombs, "row": 0, "revealed": [], "dead": False}
    )
    db.session.add(round_)
    db.session.commit()
    return jsonify(ok=True, id=round_.id, row=0, bombs=bombs)


@luck2x_bp.post("/tower/next")
@login_required
def tower_next():
    round_ = _active("tower")
    if not round_:
        return jsonify(ok=False, error="No active Tower round."), 400
    slot = int(request.json.get("slot", -1))
    state = round_.state
    if slot < 0 or slot > 4:
        return jsonify(ok=False, error="Invalid slot."), 400
    row = int(state["row"])
    if row >= 10:
        return jsonify(ok=False, error="Tower already complete."), 400
    bombs = int(state["bombs"])
    # Deterministically choose bomb slots for this row.
    slots = list(range(5))
    row_seed = state["seed"]
    for i in range(4, 0, -1):
        j = _fair_int(row_seed, f"tower-{row}-{i}", i + 1)
        slots[i], slots[j] = slots[j], slots[i]
    mine_slots = set(slots[:bombs])
    if slot in mine_slots:
        state["dead"] = True
        state["row"] = row + 1
        round_.state = state
        _finish(round_, "lost", 0)
        db.session.commit()
        return jsonify(ok=True, hit=True, row=row + 1, balance=float(_wallet().balance))
    state["row"] = row + 1
    state["revealed"] = list(state.get("revealed", [])) + [slot]
    round_.state = state
    if state["row"] >= 10:
        coeff = [1.25, 1.56, 1.95, 2.44, 3.05, 3.81, 4.77, 5.96, 7.45, 9.31][state["row"] - 1]
        payout = _money(Decimal(str(round_.bet)) * Decimal(str(coeff)) * Decimal("0.95"))
        _credit(payout, "tower")
        _finish(round_, "won", payout)
        db.session.commit()
        return jsonify(ok=True, hit=False, row=10, payout=float(payout), balance=float(_wallet().balance))
    coeffs = [1.25, 1.56, 1.95, 2.44, 3.05, 3.81, 4.77, 5.96, 7.45, 9.31]
    claim = _money(Decimal(str(round_.bet)) * Decimal(str(coeffs[state["row"] - 1])) * Decimal("0.95"))
    db.session.commit()
    return jsonify(ok=True, hit=False, row=state["row"], claim=float(claim), revealed=state["revealed"])


@luck2x_bp.post("/tower/claim")
@login_required
def tower_claim():
    round_ = _active("tower")
    if not round_:
        return jsonify(ok=False, error="No active Tower round."), 400
    row = int(round_.state["row"])
    if row < 1:
        return jsonify(ok=False, error="Open at least one level."), 400
    coeffs = [1.25, 1.56, 1.95, 2.44, 3.05, 3.81, 4.77, 5.96, 7.45, 9.31]
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(coeffs[row - 1])) * Decimal("0.95"))
    _credit(payout, "tower")
    _finish(round_, "cashed", payout)
    db.session.commit()
    return jsonify(ok=True, payout=float(payout), balance=float(_wallet().balance))


# ------------------------------ Dice ------------------------------
@luck2x_bp.post("/dice/play")
@login_required
def dice_play():
    bet = _money(request.json.get("bet", 0))
    target = float(request.json.get("target", 50))
    mode = request.json.get("mode", "over")
    if bet <= 0 or not (1 <= target <= 99) or mode not in ("over", "under"):
        return jsonify(ok=False, error="Invalid Dice parameters."), 400
    ok, err = _debit(bet, "dice")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    roll = _fair_unit(seed, "dice") * 100
    chance = (100 - target) if mode == "over" else target
    won = roll > target if mode == "over" else roll < target
    multiplier = round(0.965 / (chance / 100), 4)
    payout = _money(Decimal(str(bet)) * Decimal(str(multiplier))) if won else Decimal("0")
    if payout:
        _credit(payout, "dice")
    db.session.add(Luck2xBet(
        game="dice", user_id=current_user.id, bet=bet,
        result={"roll": round(roll, 2), "target": target, "mode": mode, "seed": seed},
        payout=payout, status="won" if won else "lost",
    ))
    db.session.commit()
    return jsonify(ok=True, roll=round(roll, 2), won=won, multiplier=multiplier,
                   payout=float(payout), balance=float(_wallet().balance))


# ------------------------------ Battle ------------------------------
@luck2x_bp.post("/battle/play")
@login_required
def battle_play():
    bet = _money(request.json.get("bet", 0))
    if bet <= 0:
        return jsonify(ok=False, error="Enter a valid bet.")
    ok, err = _debit(bet, "battle")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    player = 1 + _fair_int(seed, "player", 100)
    house = 1 + _fair_int(seed, "house", 100)
    won = player > house
    payout = _money(bet * Decimal("1.90")) if won else Decimal("0")
    if payout:
        _credit(payout, "battle")
    db.session.add(Luck2xBet(
        game="battle", user_id=current_user.id, bet=bet,
        result={"player": player, "house": house, "seed": seed},
        payout=payout, status="won" if won else "lost",
    ))
    db.session.commit()
    return jsonify(ok=True, player=player, house=house, won=won,
                   payout=float(payout), balance=float(_wallet().balance))


# ------------------------------ Wheel ------------------------------
@luck2x_bp.post("/wheel/play")
@login_required
def wheel_play():
    bet = _money(request.json.get("bet", 0))
    color = request.json.get("color")
    multipliers = {"black": 2, "red": 2, "yellow": 3, "green": 14}
    if bet <= 0 or color not in multipliers:
        return jsonify(ok=False, error="Choose a valid colour and bet."), 400
    ok, err = _debit(bet, "wheel")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    roll = _fair_unit(seed, "wheel")
    # Weighted wheel approximating Luck2x's four colour outcomes.
    if roll < 0.02:
        result = "green"
    elif roll < 0.12:
        result = "yellow"
    elif roll < 0.56:
        result = "red"
    else:
        result = "black"
    payout = _money(bet * Decimal(str(multipliers[result]))) if result == color else Decimal("0")
    if payout:
        _credit(payout, "wheel")
    db.session.add(Luck2xBet(
        game="wheel", user_id=current_user.id, bet=bet,
        result={"selected": color, "result": result, "seed": seed},
        payout=payout, status="won" if payout else "lost",
    ))
    db.session.commit()
    return jsonify(ok=True, result=result, selected=color, won=result == color,
                   payout=float(payout), balance=float(_wallet().balance))


# ------------------------------ HiLo ------------------------------
def _card(seed, index):
    n = _fair_int(seed, f"card-{index}", 52)
    return {"value": n % 13 + 1, "suit": n // 13}


@luck2x_bp.post("/hilo/start")
@login_required
def hilo_start():
    if _active("hilo"):
        return jsonify(ok=False, error="Finish your current HiLo round first.")
    bet = _money(request.json.get("bet", 0))
    if bet <= 0:
        return jsonify(ok=False, error="Enter a valid bet.")
    ok, err = _debit(bet, "hilo")
    if not ok:
        db.session.rollback()
        return jsonify(ok=False, error=err), 400
    seed = secrets.token_hex(32)
    first = _card(seed, 0)
    round_ = Luck2xGameRound(
        game="hilo", user_id=current_user.id, bet=bet,
        state={"seed": seed, "index": 0, "card": first}
    )
    db.session.add(round_)
    db.session.commit()
    return jsonify(ok=True, card=first, claim=float(bet))


@luck2x_bp.post("/hilo/flip")
@login_required
def hilo_flip():
    round_ = _active("hilo")
    if not round_:
        return jsonify(ok=False, error="No active HiLo round."), 400
    prediction = request.json.get("prediction")
    if prediction not in ("higher", "lower", "equal"):
        return jsonify(ok=False, error="Invalid prediction."), 400
    state = round_.state
    idx = int(state["index"]) + 1
    nxt = _card(state["seed"], idx)
    current = state["card"]["value"]
    if nxt["value"] > current:
        outcome = "higher"
    elif nxt["value"] < current:
        outcome = "lower"
    else:
        outcome = "equal"
    if prediction != outcome:
        _finish(round_, "lost", 0)
        db.session.commit()
        return jsonify(ok=True, next=nxt, outcome=outcome, won=False, payout=0,
                       balance=float(_wallet().balance))
    # Conservative escalating multiplier.
    multiplier = round(1.65 ** min(idx, 5) * 0.965, 4)
    state["index"] = idx
    state["card"] = nxt
    round_.state = state
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(multiplier)))
    db.session.commit()
    return jsonify(ok=True, next=nxt, outcome=outcome, won=True, multiplier=multiplier,
                   claim=float(payout))


@luck2x_bp.post("/hilo/claim")
@login_required
def hilo_claim():
    round_ = _active("hilo")
    if not round_:
        return jsonify(ok=False, error="No active HiLo round."), 400
    idx = int(round_.state["index"])
    if idx < 1:
        return jsonify(ok=False, error="Make one prediction first."), 400
    multiplier = round(1.65 ** min(idx, 5) * 0.965, 4)
    payout = _money(Decimal(str(round_.bet)) * Decimal(str(multiplier)))
    _credit(payout, "hilo")
    _finish(round_, "cashed", payout)
    db.session.commit()
    return jsonify(ok=True, payout=float(payout), balance=float(_wallet().balance))


@luck2x_bp.get("/history")
@login_required
def history():
    rows = Luck2xBet.query.filter_by(user_id=current_user.id).order_by(Luck2xBet.id.desc()).limit(50).all()
    rounds = Luck2xGameRound.query.filter_by(user_id=current_user.id).order_by(Luck2xGameRound.id.desc()).limit(50).all()
    return jsonify({
        "bets": [{"game": r.game, "bet": float(r.bet), "payout": float(r.payout),
                  "status": r.status, "created_at": r.created_at.isoformat()} for r in rows],
        "rounds": [{"game": r.game, "bet": float(r.bet), "payout": float(r.payout),
                    "status": r.status, "created_at": r.created_at.isoformat()} for r in rounds],
    })
