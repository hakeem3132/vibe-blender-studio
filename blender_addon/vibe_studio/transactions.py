"""Application-level, exact-state transactions for allowlisted object operations."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .contracts import ChangeSet


@dataclass
class Transaction:
    transaction_id: str
    change_set: ChangeSet
    target_ids: list[str]
    before_state: dict[str, Any]
    proposed_after_state: dict[str, Any] = field(default_factory=dict)
    applied_after_state: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    status: str = "PROPOSED"
    timestamp: float = field(default_factory=time.time)
    error: str | None = None
    rollback_result: dict[str, Any] | None = None


class TransactionEngine:
    def __init__(self, gateway: Any):
        self.gateway = gateway
        self.history: list[Transaction] = []
        self.pending: Transaction | None = None
        self.undo_stack: list[Transaction] = []
        self.redo_stack: list[Transaction] = []

    def _states_equal(self, expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        comparator = getattr(self.gateway, "states_equal", None)
        return bool(comparator(expected, actual)) if comparator else expected == actual

    def propose(self, change_set: ChangeSet) -> Transaction:
        self.gateway.validate_targets(change_set)
        transaction = Transaction(
            transaction_id=str(uuid.uuid4()),
            change_set=change_set,
            target_ids=list(change_set.scope.target_ids),
            before_state=self.gateway.snapshot_scene(),
        )
        self.pending = transaction
        self.history.append(transaction)
        return transaction

    def preview(self, change_set: ChangeSet) -> Transaction:
        transaction = self.propose(change_set)
        try:
            self.gateway.apply(change_set)
            transaction.proposed_after_state = self.gateway.snapshot_scene()
            transaction.verification = self.gateway.verify(change_set, transaction.before_state)
            if not transaction.verification["passed"]:
                raise RuntimeError("Deterministic preview verification failed")
            transaction.status = "PREVIEWED"
        except Exception as exc:
            transaction.status = "FAILED"
            transaction.error = str(exc)
            raise
        finally:
            self.gateway.restore_scene(transaction.before_state)
        return transaction

    def apply_pending(self) -> Transaction:
        transaction = self.pending
        if transaction is None or transaction.status not in {"PROPOSED", "PREVIEWED"}:
            raise RuntimeError("There is no valid pending change to apply")
        current = self.gateway.snapshot_scene()
        if not self._states_equal(current, transaction.before_state):
            raise RuntimeError("Scene changed after preview; refresh the proposed change")
        try:
            self.gateway.apply(transaction.change_set)
            transaction.applied_after_state = self.gateway.snapshot_scene()
            transaction.verification = self.gateway.verify(transaction.change_set, transaction.before_state)
            if not transaction.verification["passed"]:
                raise RuntimeError("Deterministic apply verification failed")
            transaction.status = "APPLIED"
            self.undo_stack.append(transaction)
            self.redo_stack.clear()
            self.pending = None
            return transaction
        except Exception as exc:
            self.gateway.restore_scene(transaction.before_state)
            transaction.status = "ROLLED_BACK"
            transaction.error = str(exc)
            transaction.rollback_result = {
                "passed": self._states_equal(self.gateway.snapshot_scene(), transaction.before_state)
            }
            self.pending = None
            raise

    def reject(self) -> Transaction:
        if self.pending is None:
            raise RuntimeError("There is no pending change to reject")
        self.pending.status = "REJECTED"
        transaction = self.pending
        self.pending = None
        return transaction

    def undo(self) -> Transaction:
        if not self.undo_stack:
            raise RuntimeError("There is no Vibe Studio change to undo")
        transaction = self.undo_stack.pop()
        self.gateway.restore_scene(transaction.before_state)
        transaction.status = "ROLLED_BACK"
        transaction.rollback_result = {
            "passed": self._states_equal(self.gateway.snapshot_scene(), transaction.before_state)
        }
        self.redo_stack.append(transaction)
        return transaction

    def redo(self) -> Transaction:
        if not self.redo_stack:
            raise RuntimeError("There is no Vibe Studio change to redo")
        transaction = self.redo_stack.pop()
        self.gateway.restore_scene(transaction.applied_after_state)
        transaction.status = "APPLIED"
        self.undo_stack.append(transaction)
        return transaction
