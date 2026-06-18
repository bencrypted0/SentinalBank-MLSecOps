Here are three test cases:

**1. Not Fraud — Small normal payment, balances match:**
```powershell
$legit = @{
    step = 200
    type = "PAYMENT"
    amount = 50.0
    oldbalanceOrg = 5000.0
    newbalanceOrig = 4950.0
    oldbalanceDest = 10000.0
    newbalanceDest = 10050.0
    errorBalanceOrig = 0.0
    errorBalanceDest = 0.0
    type_CASH_IN = 0
    type_CASH_OUT = 0
    type_DEBIT = 0
    type_PAYMENT = 1
    type_TRANSFER = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $legit -ContentType "application/json"
```

**2. Slightly Suspicious — Medium cash-out, small balance error:**
```powershell
$suspicious = @{
    step = 1
    type = "CASH_OUT"
    amount = 62000.0
    oldbalanceOrg = 62000.0
    newbalanceOrig = 0.0
    oldbalanceDest = 0.0
    newbalanceDest = 0.0
    errorBalanceOrig = 0.0
    errorBalanceDest = -62000.0
    type_CASH_IN = 0
    type_CASH_OUT = 1
    type_DEBIT = 0
    type_PAYMENT = 0
    type_TRANSFER = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $suspicious -ContentType "application/json"
```

**3. Definitely Fraud — Huge transfer, account fully drained, massive balance errors:**
```powershell
$fraud = @{
    step = 1
    type = "TRANSFER"
    amount = 3500000.0
    oldbalanceOrg = 3500000.0
    newbalanceOrig = 0.0
    oldbalanceDest = 0.0
    newbalanceDest = 0.0
    errorBalanceOrig = 0.0
    errorBalanceDest = -3500000.0
    type_CASH_IN = 0
    type_CASH_OUT = 0
    type_DEBIT = 0
    type_PAYMENT = 0
    type_TRANSFER = 1
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -Body $fraud -ContentType "application/json"
```

The key fraud signals the model learned from the PaySim data are:
- **Transaction type**: TRANSFER and CASH_OUT are riskier
- **Amount**: Very large amounts
- **Account draining**: `newbalanceOrig = 0` (entire balance sent out)
- **Destination doesn't update**: `newbalanceDest = 0` despite receiving money → large negative `errorBalanceDest`