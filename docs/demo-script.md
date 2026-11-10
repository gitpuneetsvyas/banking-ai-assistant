# Demo script

About ten minutes. Start the API and the UI using the commands in the README. Sign in only through the labelled demo buttons. All figures below are the fictional seed.

Have `backend/samples/priya_salary_slip.txt` and `backend/samples/priya_salary_slip_conflict.txt` ready. Use a fresh database if a previous run already submitted Priya's loan (`rm -rf backend/data` while the API is stopped, then start it again). The seed runs when the customer table is empty.

## Demo 1 — Balance

Sign in as Priya Sharma.

Say: `What is my bank balance?`

Expect the assistant to ask which account: savings ending 4582 or current ending 9081.

Say: `Savings`

Expect: available savings balance ₹1,25,000, account ending 4582. Point at the tool trace: `list_customer_accounts`, then `get_account_balance`. Mention the ledger is ₹1,30,000 and is not the figure shown.

## Demo 2 — Banking information

Still as Priya.

Say: `What documents are needed for a personal loan?`

Expect a checklist grounded in the personal-loan document page, with citation `DOC-PL-DOCS`. The customer did not open a form.

## Demo 3 — Formless loan

Say: `I want to apply for a ₹5 lakh loan`

Then answer in order, one message at a time:

1. `Yes` to consent. The profile card fills from KYC. She does not type her address.
2. `Salaried`
3. `Northwind Analytics`
4. `80000`
5. `36 months`
6. `Home renovation`
7. Upload `priya_salary_slip.txt`.

Expect validation to pass, a read-only PDF preview, and the Transaction PIN box. The PDF is generated from the contract. It includes Priya Sharma, ₹5,00,000, and wording that she did not fill in a form.

Enter `2580` in the Transaction PIN box and click **Confirm and submit**. Do not type the PIN into the chat.

Expect a reference `HB-PL-…`. Submit the confirmation again and show the same reference.

## Demo 4 — Security

Sign out. Sign in as Arjun Mehta.

Say: `What is my savings balance?`

Expect ₹8,750 on the account ending 2210. He has one account, so there is no clarification.

In a second session, or via the API, a request for Priya's account id returns 403. The chat will not quote her ₹1,25,000.

## Demo 5 — Accuracy

As either customer.

Say: `What is the policy on cryptocurrency trading credit lines?`

Expect an abstention. No invented product.

Say: `What documents do I need for a loan?`

Expect a clarification between personal and home loan, because both pages match and the question names neither.

## Demo 6 — Human review

Stop the API, delete `backend/data`, start again so Priya has no submitted loan. Sign in as Priya and repeat Demo 3 through purpose, but upload `priya_salary_slip_conflict.txt` (₹50,000 against the ₹80,000 she stated).

Expect status `pending_review`. The PIN does not submit.

Sign in as Demo Reviewer. Open the queue, approve with a short note.

Sign back in as Priya. The draft is waiting for confirmation. PIN `2580` submits it.

## If something looks wrong

- A second open loan is rejected until the first is submitted, rejected, or declined.
- Wrong PIN five times locks confirmation. Use a fresh database to reset.
- Home loan questions are answered from the home-loan pages and are not submitted.
