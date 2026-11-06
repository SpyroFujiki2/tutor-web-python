"""Credit wallets, cash orders, settlements and append-only transaction history."""

from app.modules.finance.ledger_guards import install_ledger_guards


install_ledger_guards()
