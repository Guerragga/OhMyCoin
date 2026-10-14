# Financial rules

## Money and dates

Amounts are finite, positive Decimal values, except fields explicitly allowing zero. Monetary columns use DECIMAL(12,2). BRL is the supported currency; there is no exchange-rate conversion. The current input parser accepts Brazilian decimal notation and ordinary dot-decimal numbers.

Dates/month filters are validated. Closing/due days beyond a month's length clamp to its final day. Supported input years are 1900–9799, leaving headroom for long schedules.

## Cards

A purchase on or before closing belongs to that closing cycle; a later purchase belongs to the next. If the due day is on/before the closing day, its invoice is due in the following month. This is a documented convention, not issuer-specific bank logic.

The base installment rounds down to cents. The final installment receives the remainder: 100 / 3 becomes 33.33, 33.33, 33.34. Splits producing a base installment below one cent are rejected.

The unified movement view excludes the backing card movement and emits the corresponding purchase once. Deleting a purchase removes its backing movement in the same transaction. Inactive cards still contribute scheduled obligations.

Estimated available limit subtracts all installments due in or after the selected month, not merely that month's invoice. Historical invoices are assumed settled. There is no invoice settlement entity, bank sync, revolving interest, refunds workflow or payment reconciliation. Changing a card's closing/due day recalculates its existing schedules.

## Debts

Each payment identifies its installment number. The aggregate paid count is not treated as the number of the last paid installment. Imported paid history assumes the first N installments were paid before tracking began; N is the aggregate count minus individually recorded payments.

A payment locks the debt, checks ownership/status/payment identity, inserts one expense and one payment record, and updates count/balance/status atomically. Paying installment 3 first does not pay installment 1.

Early payment uses the earliest unpaid installment. Its expense belongs to the actual payment date. Its future installment is marked paid and is not projected a second time.

Removing a linked debt expense reverses that payment and restores balance/status in the same transaction. Directly editing a debt expense is rejected: reverse and re-register it instead. After recorded payments, changing schedule/value/imported count requires reversing those payments first.

Debts model fixed installment amounts, not amortization/interest recalculation. Deleting a debt preserves historical expense entries but removes its schedule/payment links. That destructive action is distinct from reversing an individual payment.

## Dashboard

| Metric | Meaning |
| --- | --- |
| Real expenses | Recorded account expenses, including debt payments |
| Cash-flow balance | Recorded income minus recorded account expenses |
| Committed expenses | Manual account expenses + card installments due + debt expenses paid now + unpaid debt installments due |
| Category/payment-type evolution | Commitment-based breakdown, not a bank statement |
| Budget balance | Entered income budget minus entered expense budget, card invoices and the debt schedule |
| Capital | Account balances + separately tracked external reserves |
| Estimated net worth | Capital minus active outstanding debts and estimated remaining card installments |

Budgets are independent plans. Do not enter a card/debt commitment again as a general budget if you intend the automatic card/debt totals to cover it.

Account balances reflect all entered transactions, including future-dated entries. There is no separate pending/cleared bank ledger. Cash-flow and asset totals should therefore be interpreted as recorded/planned data, not bank-certified balances.

## Savings

Goals track money outside the listed account balances. A contribution/withdrawal changes the external reserve, not an account. To avoid counting the same asset twice, do not represent one reserve in both places. No automatic transfer workflow is implemented.

Withdrawals lock the goal and cannot exceed its balance. Completion dates are contribution-based estimates and omit interest. Extremely distant dates are left unspecified rather than overflowing the calendar.
