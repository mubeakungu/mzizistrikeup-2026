# Mzizibet — Standalone Lucky2x Edition

A self-contained Flask + SQLite Mzizibet demo containing seven Lucky2x-style games:
Crash, Mines, Tower, Dice, Battle, Wheel and HiLo.

## Windows setup

```powershell
cd mzizibet
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

If PowerShell blocks activation, run without activation:

```powershell
py -m pip install -r requirements.txt
py run.py
```

Open `http://127.0.0.1:5000`.

Register an account. New accounts receive **KES 1,000 demo balance** so the games can be tested immediately.

## Production warning

This standalone build uses SQLite and a demo deposit endpoint. It is intended as a runnable feature-complete development/demo package, not as a production real-money betting deployment. Before production, replace demo deposits with your M-Pesa Daraja integration, use PostgreSQL, add server-side authorization/rate limiting/audit controls, and independently review game math and regulatory requirements.
