# DebtLoop Bot — PoC Runtime

This repository contains the runnable Telegram proof of concept for **DebtLoop**, a B2B circular-debt detection and multilateral netting project.

The product concept and Qatar application materials are maintained in the main repository:

**AlexKlet777/DebtLoop**

## Current PoC

The bot supports:

- debt creation;
- recipient confirmation / rejection;
- debt status tracking;
- circular-debt detection across confirmed obligations;
- netting calculation without automatically changing balances;
- a built-in investor demo via `/demo`.

## Quick demo

Run the bot and send:

```
/demo
```

Expected scenario:

- Company A → Company B: $100,000
- Company B → Company C: $80,000
- Company C → Company A: $70,000
- maximum netting per link: $70,000
- gross obligations: $250,000 → $40,000

## Live PoC

Use three Telegram accounts:

1. A: `/owe @B 100000`
2. B: `/confirm ID`
3. B: `/owe @C 80000`
4. C: `/confirm ID`
5. C: `/owe @A 70000`
6. A: `/confirm ID`
7. Send `/netting`

## Notes

DebtLoop currently produces a **netting proposal**. It does not move money or legally settle obligations automatically.
