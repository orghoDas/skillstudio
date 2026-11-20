"""
Reconcile legacy payouts with the instructor wallet ledger (PAY-07).

Before 2026-11-21, instructor earnings were credited to the instructor's wallet
*and* payouts were computed from Payment.instructor_earnings, so money that was
already paid out was still sitting in the wallet. Payouts created since then
are debited from the wallet at request time (``wallet_debited=True``).

This command finds payouts that were marked ``paid`` without ever being debited
(``wallet_debited=False``) and, with ``--apply``, debits each one from the
instructor's wallet with an explanatory ledger row. It is a dry run by default.

If an instructor's wallet can't cover the debit (they already spent it), the
payout is reported and skipped; resolve those manually.
"""

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from payments.models import Payout


class Command(BaseCommand):
    help = "Debit legacy paid-but-undebited payouts from instructor wallets (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually debit the wallets.")

    def handle(self, *args, apply=False, **options):
        from students.models import Wallet

        legacy = (
            Payout.objects.filter(status="paid", wallet_debited=False)
            .select_related("instructor")
            .order_by("instructor_id", "created_at")
        )
        by_instructor = defaultdict(list)
        for payout in legacy:
            by_instructor[payout.instructor].append(payout)

        if not by_instructor:
            self.stdout.write(self.style.SUCCESS("Nothing to reconcile: every paid payout is on the wallet ledger."))
            return

        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(f"[{mode}] {sum(len(p) for p in by_instructor.values())} legacy paid payout(s) "
                          f"for {len(by_instructor)} instructor(s)")
        skipped = 0
        for instructor, payouts in by_instructor.items():
            with transaction.atomic():
                wallet, _ = Wallet.objects.get_or_create(user=instructor)
                wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
                for payout in payouts:
                    line = f"  {instructor.email}: payout #{payout.pk} ${payout.amount} (wallet ${wallet.balance})"
                    if wallet.balance < payout.amount:
                        skipped += 1
                        self.stdout.write(self.style.WARNING(line + " -> SKIPPED: insufficient wallet balance"))
                        continue
                    if apply:
                        wallet.deduct_money(
                            payout.amount,
                            description=f"Reconciliation: payout #{payout.pk} paid before the wallet ledger",
                        )
                        Payout.objects.filter(pk=payout.pk).update(wallet_debited=True)
                        self.stdout.write(line + " -> debited")
                    else:
                        wallet.balance -= payout.amount  # simulate, so later lines reflect earlier debits
                        self.stdout.write(line + " -> would debit")
                if not apply:
                    transaction.set_rollback(True)

        if skipped:
            self.stdout.write(self.style.WARNING(f"{skipped} payout(s) need manual resolution."))
        if not apply:
            self.stdout.write("Dry run only. Re-run with --apply to debit the wallets.")
