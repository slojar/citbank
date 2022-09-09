from account.models import CustomerAccount
from bankone.api import get_account_info, charge_customer


def check_balance_and_charge(user, account_no, amount, ref_code, narration):
    # CONFIRM CUSTOMER OWNS THE ACCOUNT
    if not CustomerAccount.objects.filter(customer__user=user, active=True, account_no=account_no).exists():
        return False, "Account not found"

    # CHECK ACCOUNT BALANCE
    response = get_account_info(account_no).json()
    balance = response["AvailableBalance"]

    if balance == 0:
        return False, "Insufficient balance"

    if float(amount) > balance:
        return False, "Amount cannot be greater than current balance"

    # CHARGE CUSTOMER ACCOUNT
    response = charge_customer(account_no=account_no, amount=amount, trans_ref=ref_code, description=narration)
    response = response.json()

    return True, response


